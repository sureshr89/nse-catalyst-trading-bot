"""Production cycle orchestration for the clean Dhan -> news -> S1-S5 paper path."""
from datetime import time
from pathlib import Path
import time as monotonic_time
import pandas as pd
from config.settings import (
    TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME,
    DAILY_MAX_LOSS_PER_STRATEGY, MAX_TRADES_PER_STRATEGY_PER_DAY,
    DECISION_WINDOW_SECONDS,
)
from market.news_ranker import rank as rank_news, refresh_async as refresh_news

OUTPUT = Path("outputs")
SIGNAL_FILE = OUTPUT / "signals.csv"


def _within(now, start, end):
    return time.fromisoformat(start) <= now.time() <= time.fromisoformat(end)


def _candidate(quote, ref, side):
    try:
        op = float(quote.get("TodayOpen")); hi = float(quote.get("TodayHigh")); lo = float(quote.get("TodayLow")); ltp = float(quote.get("LTP"))
        pdh = float(ref.get("PDH")); pdl = float(ref.get("PDL"))
    except (TypeError, ValueError):
        return False
    if side == "BUY":
        return ltp > op and (op > pdh or (pdl < op < pdh and lo <= pdl) or ltp > pdh)
    if side == "SELL":
        return ltp < op and (op < pdl or (pdl < op < pdh and hi >= pdh) or ltp < pdl)
    return False


def _open_allowed(engine, signal):
    strategy = str(signal.get("strategy", "")).upper()
    if strategy not in engine.daily_counts:
        return False
    if engine.daily_counts[strategy] >= MAX_TRADES_PER_STRATEGY_PER_DAY:
        return False
    if engine.daily_pnl_by_strategy.get(strategy, 0.0) <= -float(DAILY_MAX_LOSS_PER_STRATEGY):
        return False
    return True


def _sector_candidates(engine, snap, side):
    """Return stocks only from sectors moving in the current market direction."""
    prices = snap.get("prices")
    sector_map = engine.sector_map
    if not isinstance(prices, pd.DataFrame) or prices.empty or not isinstance(sector_map, pd.DataFrame) or sector_map.empty:
        return []
    p = prices[["Symbol", "change_pct"]].copy()
    p["Symbol"] = p["Symbol"].astype(str).str.upper().str.strip()
    p["change_pct"] = pd.to_numeric(p["change_pct"], errors="coerce")
    m = sector_map[["Symbol", "Sector"]].copy()
    m["Symbol"] = m["Symbol"].astype(str).str.upper().str.strip()
    merged = m.merge(p, on="Symbol", how="inner").dropna(subset=["change_pct", "Sector"])
    if merged.empty:
        return []
    sector_returns = merged.groupby("Sector")["change_pct"].mean()
    if side == "BUY":
        eligible = set(sector_returns[sector_returns > 0].index)
    else:
        eligible = set(sector_returns[sector_returns < 0].index)
    return merged.loc[merged["Sector"].isin(eligible), "Symbol"].drop_duplicates().tolist()


def _try_stock(engine, symbol, ref, snap, side, now):
    """Evaluate the unchanged S1-S5 logic after news/sector prioritization."""
    local_snap = dict(snap)
    local_snap["intraday"] = {}
    signals = engine._evaluate_stock(symbol, ref, local_snap)
    if not signals:
        try:
            intraday = engine.price_data.get_1m(symbol)
        except Exception:
            intraday = pd.DataFrame()
        if intraday is not None and not intraday.empty:
            local_snap["intraday"] = {symbol: intraday}
            signals = engine._evaluate_stock(symbol, ref, local_snap)
    for signal in signals:
        if not _open_allowed(engine, signal):
            continue
        trade = dict(signal)
        trade.update({"approved": True, "entry_time": now})
        opened = engine.paper_engine.open_trade(trade)
        if opened.get("opened"):
            strategy = str(signal.get("strategy", "")).upper()
            engine.daily_counts[strategy] += 1
            signal["trade_id"] = opened.get("trade_id")
            return signal
    return None


def run_cycle(engine):
    """Run one fresh 15-second collection + <=10-second decision cycle."""
    now = engine.now()
    if not _within(now, "09:15", "15:30"):
        return []

    # _market_snapshot always starts a new full-NIFTY-500 quote request when
    # the 25-second worker cycle fires. The 98% gate remains authoritative.
    snap = engine._market_snapshot()
    decision_started = monotonic_time.monotonic()
    decision_deadline = decision_started + DECISION_WINDOW_SECONDS
    engine.diagnostics["decision_budget_seconds"] = DECISION_WINDOW_SECONDS
    engine.diagnostics["decision_started_at"] = now.isoformat(timespec="seconds")

    if not snap.get("trade_ready"):
        engine.diagnostics["decision_elapsed_seconds"] = round(monotonic_time.monotonic() - decision_started, 3)
        engine.diagnostics["decision_deadline_met"] = True
        engine._write_diagnostics()
        return []

    for symbol in list(engine.paper_engine.open_positions):
        quote = snap.get("dhan_quotes", {}).get(symbol, {})
        if quote:
            engine.paper_engine.process_live_price(symbol, quote.get("LTP"), timestamp=now,
                                                    high=quote.get("TodayHigh"), low=quote.get("TodayLow"))

    if now.time() >= time.fromisoformat(SQUARE_OFF_TIME):
        for symbol in list(engine.paper_engine.open_positions):
            ltp = snap.get("dhan_quotes", {}).get(symbol, {}).get("LTP")
            if ltp:
                engine.paper_engine.close_position(symbol, ltp, now, "FORCE_SQUARE_OFF_15:00")
        engine.diagnostics["decision_elapsed_seconds"] = round(monotonic_time.monotonic() - decision_started, 3)
        engine.diagnostics["decision_deadline_met"] = monotonic_time.monotonic() <= decision_deadline
        engine._write_diagnostics()
        return []
    if not _within(now, TRADING_START, LAST_ENTRY_TIME):
        return []

    side = "BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else None
    if side is None:
        return []

    # Sector filtering happens before stock selection. News is refreshed in the
    # background and the latest cached news is used immediately, so external
    # news latency cannot consume the 10-second trade-decision budget.
    sector_symbols = _sector_candidates(engine, snap, side)
    refresh_news(sector_symbols)
    ranked_news = rank_news(sector_symbols, side)
    ranked_symbols = [symbol for symbol, _score in ranked_news]
    engine.diagnostics["sector_candidate_stocks"] = len(sector_symbols)
    engine.diagnostics["news_ranked_stocks"] = len(ranked_symbols)

    ref_by_symbol = {
        str(r.get("Symbol", "")).upper().strip(): r
        for _, r in engine.references.iterrows()
    }
    signals = []
    # Only stocks with matching news are eligible. They are processed strictly
    # in descending news-strength order; the existing strategy rules remain the
    # final confirmation and entry/exit authority.
    for symbol in ranked_symbols:
        if monotonic_time.monotonic() > decision_deadline:
            engine.diagnostics["decision_deadline_met"] = False
            break
        if not symbol or symbol not in ref_by_symbol or engine.paper_engine.has_open_position(symbol):
            continue
        ref = ref_by_symbol[symbol]
        quote = snap.get("dhan_quotes", {}).get(symbol, {})
        if not quote or not _candidate(quote, ref, side):
            continue
        signal = _try_stock(engine, symbol, ref, snap, side, now)
        if signal is not None:
            signals.append(signal)

    engine.last_signals = signals
    engine.diagnostics["final_signals"] = len(signals)
    engine.diagnostics["signals_by_strategy"] = {s: sum(1 for x in signals if str(x.get("strategy", "")).upper() == s) for s in engine.daily_counts}
    engine.diagnostics["trade_path_status"] = "READY" if signals or snap.get("buy_alignment") or snap.get("sell_alignment") else "BLOCKED"
    engine.diagnostics["decision_elapsed_seconds"] = round(monotonic_time.monotonic() - decision_started, 3)
    engine.diagnostics["decision_deadline_met"] = engine.diagnostics.get("decision_deadline_met", True) and monotonic_time.monotonic() <= decision_deadline
    engine._write_diagnostics()
    if signals:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(signals).to_csv(SIGNAL_FILE, index=False)
    return signals
