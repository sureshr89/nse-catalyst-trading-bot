"""Build persistent master datasets for the rolling six-month research window.

The master files are append/upsert style and automatically retain only the
current month plus the previous five calendar months. This keeps the Streamlit
Cloud files small while always preserving the latest six months of data.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
MASTER_MONTHS = 6

MASTER_STOCK = OUTPUT / "MASTER_DAILY_STOCK_DATA.csv"
MASTER_TRADES = OUTPUT / "MASTER_TRADES.csv"
MASTER_DAILY = OUTPUT / "MASTER_DAILY_SUMMARY.csv"


def _read(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _write(path, df):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _merge(path, new, keys):
    if new.empty:
        return
    old = _read(path)
    combined = pd.concat([old, new], ignore_index=True) if not old.empty else new.copy()
    for key in keys:
        if key not in combined.columns:
            combined[key] = ""
    combined = combined.drop_duplicates(subset=keys, keep="last")
    _write(path, combined)


def _prune_to_last_six_months(path, date_columns):
    """Keep only the current calendar month and five preceding months."""
    frame = _read(path)
    if frame.empty:
        return

    date_values = None
    for column in date_columns:
        if column in frame.columns:
            parsed = pd.to_datetime(frame[column], errors="coerce")
            if parsed.notna().any():
                date_values = parsed
                break

    if date_values is None:
        return

    now = datetime.now(IST)
    current_period = pd.Period(now.strftime("%Y-%m"), freq="M")
    first_period = current_period - (MASTER_MONTHS - 1)
    row_periods = date_values.dt.to_period("M")

    # Keep undated rows rather than deleting them accidentally.
    keep = date_values.isna() | ((row_periods >= first_period) & (row_periods <= current_period))
    trimmed = frame.loc[keep].copy()

    if len(trimmed) != len(frame):
        _write(path, trimmed)


def enforce_six_month_retention():
    """Prune all durable master datasets to a rolling six-month window."""
    _prune_to_last_six_months(MASTER_STOCK, ["TradeDate", "DataSnapshotIST"])
    _prune_to_last_six_months(MASTER_TRADES, ["TradeDate", "entry_time", "exit_time", "timestamp"])
    _prune_to_last_six_months(MASTER_DAILY, ["TradeDate", "PreparedAtIST"])


def build_master_data():
    """Snapshot today's gap/scanner/trade data and enforce six-month retention."""
    today = datetime.now(IST).strftime("%Y-%m-%d")
    gaps = _read(OUTPUT / "gap_analysis.csv")
    trades = _read(OUTPUT / "trades.csv")
    signals = _read(OUTPUT / "signals.csv")
    try:
        diag = json.loads((OUTPUT / "scanner_diagnostics.json").read_text(encoding="utf-8"))
    except Exception:
        diag = {}

    if not gaps.empty and "Symbol" in gaps.columns:
        stock = gaps.copy()
        stock.insert(0, "TradeDate", today)
        stock["DataSnapshotIST"] = datetime.now(IST).isoformat(timespec="seconds")
        _merge(MASTER_STOCK, stock, ["TradeDate", "Symbol"])

    if not trades.empty:
        t = trades.copy()
        date_col = next((c for c in ["entry_time", "exit_time", "timestamp"] if c in t.columns), None)
        t.insert(0, "TradeDate", t[date_col].astype(str).str[:10] if date_col else today)
        _merge(
            MASTER_TRADES,
            t,
            ["TradeDate", "symbol", "entry_time", "signal", "entry"] if "symbol" in t.columns else ["TradeDate"],
        )

    row = {
        "TradeDate": today,
        "PreparedAtIST": datetime.now(IST).isoformat(timespec="seconds"),
        "StocksInGapBoard": int(len(gaps)),
        "GapUps": int((gaps.get("GapType", pd.Series(dtype=str)) == "GAP_UP").sum()),
        "GapDowns": int((gaps.get("GapType", pd.Series(dtype=str)) == "GAP_DOWN").sum()),
        "SignalsRecorded": int(len(signals)),
        "TradesRecorded": int(len(trades)),
        "ClosedTrades": int((trades.get("status", pd.Series(dtype=str)).astype(str).str.upper() == "CLOSED").sum()),
        "FinalSignals": int(diag.get("final_signals", 0) or 0),
        "StocksScanned": int(diag.get("stocks_scanned", 0) or 0),
        "LiquidityPassed": int(diag.get("liquidity_passed", 0) or 0),
        "OpeningSetupPassed": int(diag.get("opening_setup_passed", 0) or 0),
        "MarketAlignmentPassed": int(diag.get("market_alignment_passed", 0) or 0),
        "SectorAlignmentPassed": int(diag.get("sector_alignment_passed", 0) or 0),
        "StrategySetupPassed": int(diag.get("strategy_setup_passed", 0) or 0),
        "StockAlignmentPassed": int(diag.get("stock_alignment_passed", 0) or 0),
        "DailyPnL": float(pd.to_numeric(trades.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
    }
    _merge(MASTER_DAILY, pd.DataFrame([row]), ["TradeDate"])

    # Retention runs after every refresh, so old master records cannot grow indefinitely.
    enforce_six_month_retention()

    return {"stock": str(MASTER_STOCK), "trades": str(MASTER_TRADES), "daily": str(MASTER_DAILY)}
