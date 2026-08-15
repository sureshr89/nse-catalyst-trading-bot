"""Build persistent master datasets for the rolling six-month research window."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd
from papertrade.persistent_storage import restore, sync

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
MASTER_MONTHS = 6
MASTER_STOCK = OUTPUT / "MASTER_DAILY_STOCK_DATA.csv"
MASTER_TRADES = OUTPUT / "MASTER_TRADES.csv"
MASTER_NEWS = OUTPUT / "MASTER_NEWS_ANALYSIS.csv"
MASTER_DAILY = OUTPUT / "MASTER_DAILY_SUMMARY.csv"
NEWS_FIELDS = ["TradeDate", "timestamp", "candidate_id", "symbol", "signal", "candidate_state", "approved", "news_sentiment", "news_confidence", "news_headline", "news_reason", "news_source", "news_checked_at", "nifty500_change_pct", "entry", "stop_loss", "target", "quantity", "risk_per_share", "actual_risk", "atr_pct", "priority_rank", "setup_type", "gap_percent", "reason"]

def _read(path):
    try: return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception: return pd.DataFrame()

def _write(path, df):
    OUTPUT.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp"); df.to_csv(tmp, index=False); tmp.replace(path)

def _restore_if_missing(path, repo_path):
    if path.exists() and path.stat().st_size > 0: return
    try: restore(path, repo_path)
    except Exception as error: print("Master restore skipped:", error)

def _merge(path, new, keys):
    if new.empty: return
    old = _read(path); combined = pd.concat([old, new], ignore_index=True) if not old.empty else new.copy()
    for key in keys:
        if key not in combined.columns: combined[key] = ""
    _write(path, combined.drop_duplicates(subset=keys, keep="last"))

def _trade_merge(new):
    if new.empty: return
    old = _read(MASTER_TRADES); combined = pd.concat([old, new], ignore_index=True) if not old.empty else new.copy()
    if "trade_id" in combined.columns:
        ids = combined["trade_id"].astype(str).str.strip(); has_id = ids.ne("") & ids.ne("nan")
        with_id = combined.loc[has_id].drop_duplicates(subset=["trade_id"], keep="last"); without_id = combined.loc[~has_id].copy()
        fallback = [c for c in ["TradeDate", "symbol", "entry_time", "signal", "entry"] if c in without_id.columns]
        if fallback: without_id = without_id.drop_duplicates(subset=fallback, keep="last")
        combined = pd.concat([with_id, without_id], ignore_index=True)
    else:
        fallback = [c for c in ["TradeDate", "symbol", "entry_time", "signal", "entry"] if c in combined.columns]
        if fallback: combined = combined.drop_duplicates(subset=fallback, keep="last")
    _write(MASTER_TRADES, combined)

def _month_values(frame, columns):
    for column in columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce")
            if values.notna().any(): return values.dt.strftime("%Y-%m")
    return pd.Series([None] * len(frame), index=frame.index, dtype="object")

def _prune_to_last_six_months(path, date_columns):
    frame = _read(path)
    if frame.empty: return
    months = _month_values(frame, date_columns); now = datetime.now(IST); current_period = pd.Period(now.strftime("%Y-%m"), freq="M"); first_period = current_period - (MASTER_MONTHS - 1)
    allowed = {str(p) for p in pd.period_range(first_period, current_period, freq="M")}; trimmed = frame.loc[months.isna() | months.isin(allowed)].copy()
    if len(trimmed) != len(frame): _write(path, trimmed)

def enforce_six_month_retention():
    _prune_to_last_six_months(MASTER_STOCK, ["TradeDate", "DataSnapshotIST"])
    _prune_to_last_six_months(MASTER_TRADES, ["TradeDate", "entry_time", "exit_time", "timestamp"])
    _prune_to_last_six_months(MASTER_NEWS, ["TradeDate", "timestamp", "news_checked_at"])
    _prune_to_last_six_months(MASTER_DAILY, ["TradeDate", "PreparedAtIST"])

def _today_rows(frame, date_columns, today):
    if frame.empty: return frame
    for column in date_columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce")
            if values.notna().any(): return frame.loc[values.dt.strftime("%Y-%m-%d").eq(today)].copy()
    return frame.iloc[0:0].copy()

def _closed_unique(frame):
    if frame.empty or "status" not in frame.columns: return frame.iloc[0:0].copy()
    closed = frame[frame["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if closed.empty: return closed
    if "trade_id" in closed.columns:
        ids = closed["trade_id"].astype(str).str.strip(); has_id = ids.ne("") & ids.ne("nan")
        with_id = closed.loc[has_id].drop_duplicates(subset=["trade_id"], keep="last"); without_id = closed.loc[~has_id].copy()
        fallback = [c for c in ["symbol", "entry_time", "signal", "entry"] if c in without_id.columns]
        if fallback: without_id = without_id.drop_duplicates(subset=fallback, keep="last")
        return pd.concat([with_id, without_id], ignore_index=True)
    fallback = [c for c in ["symbol", "entry_time", "signal", "entry"] if c in closed.columns]
    return closed.drop_duplicates(subset=fallback, keep="last") if fallback else closed

def _build_news_history(signals, today):
    if signals.empty: return pd.DataFrame(columns=NEWS_FIELDS)
    frame = signals.copy()
    for column in NEWS_FIELDS:
        if column not in frame.columns: frame[column] = ""
    frame["TradeDate"] = pd.to_datetime(frame["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(today)
    frame = frame[NEWS_FIELDS].copy(); key = [c for c in ["TradeDate", "candidate_id", "symbol", "signal"] if c in frame.columns]
    return frame.drop_duplicates(subset=key, keep="last") if key else frame.drop_duplicates()

def _approved_mask(frame):
    if frame.empty or "approved" not in frame.columns: return pd.Series(False, index=frame.index)
    return frame["approved"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])

def build_master_data():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _restore_if_missing(MASTER_STOCK, "outputs/MASTER_DAILY_STOCK_DATA.csv"); _restore_if_missing(MASTER_TRADES, "outputs/MASTER_TRADES.csv"); _restore_if_missing(MASTER_NEWS, "outputs/MASTER_NEWS_ANALYSIS.csv"); _restore_if_missing(MASTER_DAILY, "outputs/MASTER_DAILY_SUMMARY.csv")
    today = datetime.now(IST).strftime("%Y-%m-%d"); gaps = _read(OUTPUT / "gap_analysis.csv"); trades = _read(OUTPUT / "trades.csv"); signals = _read(OUTPUT / "signals.csv")
    try: diag = json.loads((OUTPUT / "scanner_diagnostics.json").read_text(encoding="utf-8"))
    except Exception: diag = {}
    if not gaps.empty and "Symbol" in gaps.columns:
        stock = gaps.copy().drop(columns=["TradeDate"], errors="ignore"); stock.insert(0, "TradeDate", today); stock["DataSnapshotIST"] = datetime.now(IST).isoformat(timespec="seconds"); _merge(MASTER_STOCK, stock, ["TradeDate", "Symbol"])
    if not trades.empty:
        t = trades.copy().drop(columns=["TradeDate"], errors="ignore"); date_col = next((c for c in ["entry_time", "exit_time", "timestamp"] if c in t.columns), None); t.insert(0, "TradeDate", t[date_col].astype(str).str[:10] if date_col else today); _trade_merge(t)
    news_history = _build_news_history(signals, today)
    if not news_history.empty: _merge(MASTER_NEWS, news_history, ["TradeDate", "candidate_id", "symbol", "signal"])
    today_trades = _today_rows(trades, ["entry_time", "timestamp", "exit_time"], today); today_closed = _closed_unique(_today_rows(trades, ["exit_time"], today)); today_signals = _today_rows(signals, ["timestamp", "entry_time"], today); today_news = _today_rows(news_history, ["TradeDate", "timestamp"], today)
    today_pnl = float(pd.to_numeric(today_closed.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()); gap_types = gaps.get("GapType", pd.Series(dtype=str)).astype(str).str.upper(); sentiment = today_news.get("news_sentiment", pd.Series(dtype=str)).astype(str).str.upper(); approved = _approved_mask(today_news)
    row = {
        "TradeDate": today, "PreparedAtIST": datetime.now(IST).isoformat(timespec="seconds"), "StocksInGapBoard": int(len(gaps)), "GapUps": int(gap_types.eq("GAP_UP").sum()), "GapDowns": int(gap_types.eq("GAP_DOWN").sum()),
        "SignalsRecorded": int(len(today_signals)), "TradesRecorded": int(len(today_trades)), "ClosedTrades": int(len(today_closed)), "NewsDecisions": int(len(today_news)),
        "NewsPositive": int(sentiment.eq("POSITIVE").sum()), "NewsNegative": int(sentiment.eq("NEGATIVE").sum()), "NewsNeutral": int(sentiment.eq("NEUTRAL").sum()), "NewsPassed": int(approved.sum()), "NewsRejected": int((~approved).sum()),
        "FinalSignals": int(diag.get("final_signals", 0) or 0), "StocksScanned": int(diag.get("stocks_scanned", 0) or 0), "OpeningSetupPassed": int(diag.get("opening_setup_passed", 0) or 0), "MarketFilterPassed": int(diag.get("market_alignment_passed", 0) or 0), "StrategySetupPassed": int(diag.get("strategy_setup_passed", 0) or 0), "Nifty500ChangePct": float(diag.get("nifty500_change_pct", 0) or 0), "DailyPnL": round(today_pnl, 2)
    }
    _merge(MASTER_DAILY, pd.DataFrame([row]), ["TradeDate"]); enforce_six_month_retention()
    for path in (MASTER_STOCK, MASTER_TRADES, MASTER_NEWS, MASTER_DAILY):
        try: sync(path, f"outputs/{path.name}", f"Update master trading data {today}")
        except Exception as error: print("Master data sync skipped:", error)
    return {"stock": str(MASTER_STOCK), "trades": str(MASTER_TRADES), "news": str(MASTER_NEWS), "daily": str(MASTER_DAILY)}
