"""Shared read-only data helpers for every Strategy 2 dashboard page.

Strategy 2 is executed only by TradingBot in bot_runner.py. The old
strategy2_worker.py status file is not used for live dashboard state.
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

S2_TRADES = OUTPUTS / "strategy2_trades.csv"
S2_SIGNALS = OUTPUTS / "strategy2_signals.csv"
S2_STATUS = OUTPUTS / "strategy2_status.json"  # legacy only
S2_DIAGNOSTICS = OUTPUTS / "strategy2_diagnostics.json"
S2_STATE = OUTPUTS / "strategy2_paper_engine_state.json"
GAPS = OUTPUTS / "strategy2_gap_analysis.csv"
BOT_STATUS = OUTPUTS / "bot_status.json"

STARTING_CAPITAL = 250000.0


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def read_csv(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def diagnostics():
    return read_json(S2_DIAGNOSTICS)


def state():
    return read_json(S2_STATE)


def status():
    """Build Strategy 2 live status from the single TradingBot owner."""
    bot = read_json(BOT_STATUS)
    diag = diagnostics()
    paper = state()
    if not bot and not diag and not paper:
        return {"status": "STARTING", "message": "Paper bot has not produced live Strategy 2 state yet."}

    bot_status = str(bot.get("status", "STARTING"))
    s2_status = "ERROR" if bot_status == "ERROR" else bot_status
    open_positions = paper.get("open_positions", {}) or {}
    return {
        "status": s2_status,
        "message": f"Strategy 2 is owned by the single NIFTY 500 paper-bot worker. Overall bot: {bot_status}.",
        "last_scan": diag.get("timestamp"),
        "last_signal_count": int(diag.get("signals", 0) or 0),
        "available_capital": float(paper.get("available_capital", STARTING_CAPITAL) or STARTING_CAPITAL),
        "total_capital": float(paper.get("total_capital", STARTING_CAPITAL) or STARTING_CAPITAL),
        "open_positions": len(open_positions),
        "daily_pnl": float(diag.get("daily_pnl", 0.0) or 0.0),
        "last_error": bot.get("last_scan_error") or bot.get("error"),
        "worker_alive": bool(bot.get("worker_alive", False)),
        "heartbeat": bot.get("heartbeat"),
    }


def trades():
    return read_csv(S2_TRADES)


def signals():
    return read_csv(S2_SIGNALS)


def gaps():
    return read_csv(GAPS)


def closed_trades():
    df = trades()
    if df.empty or "status" not in df.columns:
        return pd.DataFrame()
    result = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if "pnl" in result.columns:
        result["pnl"] = pd.to_numeric(result["pnl"], errors="coerce").fillna(0.0)
    return result


def format_price(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "—"


def format_pct(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "—"


def today_signals(df=None):
    df = signals() if df is None else df.copy()
    if df.empty:
        return df
    date_col = "entry_time" if "entry_time" in df.columns else "timestamp" if "timestamp" in df.columns else None
    if not date_col:
        return df.iloc[0:0]
    dates = pd.to_datetime(df[date_col], errors="coerce")
    if getattr(dates.dt, "tz", None) is None:
        dates = dates.dt.tz_localize("Asia/Kolkata")
    else:
        dates = dates.dt.tz_convert("Asia/Kolkata")
    return df.loc[dates.dt.date.eq(pd.Timestamp.now(tz="Asia/Kolkata").date())].copy()


def approved_today():
    df = today_signals()
    if df.empty or "approved" not in df.columns:
        return df.iloc[0:0] if not df.empty else df
    return df[df["approved"].astype(str).str.lower().isin({"true", "1", "yes"})].copy()
