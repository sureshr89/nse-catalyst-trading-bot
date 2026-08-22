"""Production cycle orchestration for the clean Dhan -> news -> S1-S5 paper path."""
from datetime import time
from pathlib import Path
import time as monotonic_time
import pandas as pd
from config.settings import (
    TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME,
    DAILY_MAX_LOSS_PER_STRATEGY, MAX_TRADES_PER_STRATEGY_PER_DAY,
    COLLECTION_WINDOW_SECONDS, DECISION_WINDOW_SECONDS, MIN_DATA_COVERAGE_COUNT,
)
from market.news_ranker import rank as rank_news, refresh_async as refresh_news, snapshot as news_snapshot

OUTPUT = Path("outputs")
SIGNAL_FILE = OUTPUT / "signals.csv"


def _within(now, start, end):
    return time.fromisoformat(start) <= now.time() <= time.fromisoformat(end)


def _candidate(quote, ref, side):
    """Validate only data needed by the cycle; never duplicate S1-S5 rules.

    In particular, today's high/low already include the current LTP. Therefore
    ``LTP > TodayHigh`` and ``LTP < TodayLow`` can never be reliable S4 gates.
    S4 uses completed intraday history inside MasterEngine._evaluate_stock(), so
    this cycle-level filter must not pre-reject a valid S4 candidate.
    """
    try:
        op = float(quote.get("TodayOpen")); hi = float(quote.get("TodayHigh")); lo = float(quote.get("TodayLow")); ltp = float(quote.get("LTP"))
        pdh = float(ref.get("PDH")); pdl = float(ref.get("PDL"))
    except (TypeError, ValueError):
        return False
    values = (op, hi, lo, ltp, pdh, pdl)
    if not all(x == x and abs(x) != float("inf") for x in values):
        return False
    if pdl >= pdh or min(op, hi, lo, ltp, pdh, pdl) <= 0:
        return False
    side = str(side).upper().strip()
    if side not in {"BUY", "SELL"}:
        return False
    # This is intentionally a validation-only superset filter. The authoritative
    # evaluator decides S1-S5 and their exact entry conditions.
    return True


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
    if side == "BUY": eligible = set(sector_returns[sector_returns > 0].index)
    else: eligible = set(sector_returns[sector_returns < 0].index)
    return merged.loc[merged["Sector"].isin(eligible), "Symbol"].drop_duplicates().tolist()


def _try_stock(engine, symbol, ref, snap, side, now, news_meta=None):
    signals = engine._evaluate_stock(symbol, ref, snap)
    for signal in signals:
        if not _open_allowed(engine, signal): continue
        trade = dict(signal)
        if news_meta:
            trade.update(news_meta); signal.update(news_meta)
        trade.update({"approved": True, "entry_time": now})
        opened = engine.paper_engine.open_trade(trade)
        if opened.get("opened"):
            strategy = str(signal.get("strategy", "")).upper(); engine.daily_counts[strategy] += 1
            signal["trade_id"] = opened.get("trade_id")
            return signal
    return None


def _invalidate_cycle(engine, reason, collected_count=0, elapsed=None):
    engine.diagnostics.update({"trade_ready": False,"trade_data_verified": False,"buy_alignment": False,"sell_alignment": False,"trade_path_status": "BLOCKED","market_data_coverage": f"{int(collected_count)}/500","collection_window_seconds": COLLECTION_WINDOW_SECONDS,"collection_elapsed_seconds": None if elapsed is None else round(float(elapsed), 3),"collection_valid": False,"no_trade_reason": reason})
    engine.diagnostics.setdefault("rejections", {})["collection_gate"] = reason; engine.last_snapshot = {}; engine.last_signals = []; engine._write_diagnostics(); return []


def _force_square_off(engine, snap, now):
    if now.time() < time.fromisoformat(SQUARE_OFF_TIME): return False
    quotes = snap.get("dhan_quotes", {}) if isinstance(snap, dict) else {}; used_fallback = False
    for symbol in list(engine.paper_engine.open_positions):
        quote = quotes.get(symbol, {}) or {}; ltp = quote.get("LTP"); reason = "FORCE_SQUARE_OFF_15:00"
        if ltp: engine.paper_engine.process_live_price(symbol, ltp, timestamp=now, high=quote.get("TodayHigh"), low=quote.get("TodayLow"))
        if not engine.paper_engine.has_open_position(symbol): continue
        if not ltp:
            position = engine.paper_engine.open_positions.get(symbol, {}); ltp = position.get("last_live_price") or position.get("entry"); reason = "FORCE_SQUARE_OFF_15:00_LAST_KNOWN_PRICE"; used_fallback = True
        if ltp: engine.paper_engine.close_position(symbol, ltp, now, reason)
    engine.diagnostics["trade_path_status"] = "BLOCKED"; engine.diagnostics["no_trade_reason"] = "MANDATORY_SQUARE_OFF_15:00"; engine.diagnostics["square_off_completed"] = not bool(engine.paper_engine.open_positions); engine.diagnostics["square_off_used_fallback_price"] = used_fallback; engine._write_diagnostics(); return True


def run_cycle(engine):
    """Run one fresh collection + bounded decision cycle."""
    now = engine.now()
    if not _within(now, "09:15", "15:30"): return []
    collection_started = monotonic_time.monotonic(); snap = engine._market_snapshot(); collection_elapsed = monotonic_time.monotonic() - collection_started
    quotes = snap.get("dhan_quotes", {}) if isinstance(snap, dict) else {}; collected_count = len(quotes)
    if _force_square_off(engine, snap, now): return []
    if collection_elapsed > COLLECTION_WINDOW_SECONDS: return _invalidate_cycle(engine, f"COLLECTION_TIMEOUT_{collection_elapsed:.3f}s>{COLLECTION_WINDOW_SECONDS}s", collected_count, collection_elapsed)
    if collected_count < MIN_DATA_COVERAGE_COUNT: return _invalidate_cycle(engine, f"INSUFFICIENT_FRESH_QUOTES_{collected_count}/500_BELOW_{MIN_DATA_COVERAGE_COUNT}", collected_count, collection_elapsed)
    if not snap.get("trade_ready"): return _invalidate_cycle(engine, "MARKET_SNAPSHOT_NOT_TRADE_READY", collected_count, collection_elapsed)
    decision_started = monotonic_time.monotonic(); decision_deadline = decision_started + DECISION_WINDOW_SECONDS
    engine.diagnostics.update({"collection_window_seconds": COLLECTION_WINDOW_SECONDS,"collection_elapsed_seconds": round(collection_elapsed,3),"collection_valid": True,"decision_budget_seconds": DECISION_WINDOW_SECONDS,"decision_started_at": engine.now().isoformat(timespec="seconds"),"decision_deadline_met": True})
    for symbol in list(engine.paper_engine.open_positions):
        quote = snap.get("dhan_quotes", {}).get(symbol, {})
        if quote: engine.paper_engine.process_live_price(symbol, quote.get("LTP"), timestamp=now, high=quote.get("TodayHigh"), low=quote.get("TodayLow"))
    if not _within(now, TRADING_START, LAST_ENTRY_TIME):
        engine.diagnostics["trade_path_status"]="BLOCKED"; engine.diagnostics["no_trade_reason"]="OUTSIDE_ENTRY_WINDOW"; engine.diagnostics["decision_elapsed_seconds"]=round(monotonic_time.monotonic()-decision_started,3); engine.diagnostics["decision_deadline_met"]=monotonic_time.monotonic()<=decision_deadline; engine._write_diagnostics(); return []
    side = "BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else None
    if side is None: engine.diagnostics["decision_elapsed_seconds"]=round(monotonic_time.monotonic()-decision_started,3); engine._write_diagnostics(); return []
    sector_symbols = _sector_candidates(engine, snap, side); refresh_news(sector_symbols); ranked_news = rank_news(sector_symbols, side); ranked_symbols = [symbol for symbol,_score in ranked_news]; news_cache = news_snapshot(); news_meta_by_symbol={}
    for rank_position,symbol in enumerate(ranked_symbols,1):
        item=news_cache.get(symbol,{ }); headlines=item.get("headlines") or []; score=float(item.get("score",0.0) or 0.0); latest=max(headlines,key=lambda h:str(h.get("published",""))) if headlines else {}; news_meta_by_symbol[symbol]={"news_available":bool(headlines),"news_sentiment":"POSITIVE" if score>0 else "NEGATIVE" if score<0 else "NEUTRAL","news_strength_score":round(abs(score),2),"news_signed_score":round(score,2),"news_priority_rank":rank_position,"news_headline":str(latest.get("title","")),"news_published":str(latest.get("published","")),"news_source":str(latest.get("source","")),"news_headline_count":len(headlines),"news_selected_at":now.isoformat(timespec="seconds")}
    engine.diagnostics["sector_candidate_stocks"]=len(sector_symbols); engine.diagnostics["news_ranked_stocks"]=len(ranked_symbols)
    snap=dict(snap); snap["intraday"]=engine.prepare_intraday_for_symbols(ranked_symbols,decision_deadline) if hasattr(engine,"prepare_intraday_for_symbols") else {}
    ref_by_symbol={str(r.get("Symbol","")).upper().strip():r for _,r in engine.references.iterrows()}; signals=[]
    for symbol in ranked_symbols:
        if monotonic_time.monotonic()>decision_deadline: engine.diagnostics["decision_deadline_met"]=False; break
        if not symbol or symbol not in ref_by_symbol or engine.paper_engine.has_open_position(symbol): continue
        ref=ref_by_symbol[symbol]; quote=snap.get("dhan_quotes",{}).get(symbol,{})
        if not quote or not _candidate(quote,ref,side): continue
        signal=_try_stock(engine,symbol,ref,snap,side,now,news_meta_by_symbol.get(symbol))
        if signal is not None: signals.append(signal)
    engine.last_signals=signals; engine.diagnostics["final_signals"]=len(signals); engine.diagnostics["signals_by_strategy"]={s:sum(1 for x in signals if str(x.get("strategy","")).upper()==s) for s in engine.daily_counts}; engine.diagnostics["trade_path_status"]="READY" if signals else "BLOCKED"; engine.diagnostics["no_trade_reason"]="NO_ELIGIBLE_S1_S5_SETUP" if not signals else None; engine.diagnostics["decision_elapsed_seconds"]=round(monotonic_time.monotonic()-decision_started,3); engine.diagnostics["decision_deadline_met"]=engine.diagnostics.get("decision_deadline_met",True) and monotonic_time.monotonic()<=decision_deadline; engine._write_diagnostics()
    if signals: OUTPUT.mkdir(parents=True,exist_ok=True); pd.DataFrame(signals).to_csv(SIGNAL_FILE,index=False)
    return signals
