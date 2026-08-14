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


def _restore_if_missing(path, repo_path):
    """Restore durable master data only when the local file is absent/empty."""
    if path.exists() and path.stat().st_size > 0:
        return
    try:
        restore(path, repo_path)
    except Exception as error:
        print("Master restore skipped:", error)


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


def _month_values(frame, columns):
    for column in columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce")
            if values.notna().any():
                return values.dt.strftime("%Y-%m")
    return pd.Series([None] * len(frame), index=frame.index, dtype="object")


def _prune_to_last_six_months(path, date_columns):
    frame = _read(path)
    if frame.empty:
        return
    months = _month_values(frame, date_columns)
    now = datetime.now(IST)
    current_period = pd.Period(now.strftime("%Y-%m"), freq="M")
    first_period = current_period - (MASTER_MONTHS - 1)
    allowed = {str(p) for p in pd.period_range(first_period, current_period, freq="M")}
    keep = months.isna() | months.isin(allowed)
    trimmed = frame.loc[keep].copy()
    if len(trimmed) != len(frame):
        _write(path, trimmed)


def enforce_six_month_retention():
    _prune_to_last_six_months(MASTER_STOCK, ["TradeDate", "DataSnapshotIST"])
    _prune_to_last_six_months(MASTER_TRADES, ["TradeDate", "entry_time", "exit_time", "timestamp"])
    _prune_to_last_six_months(MASTER_DAILY, ["TradeDate", "PreparedAtIST"])


def _today_rows(frame, date_columns, today):
    if frame.empty:
        return frame
    for column in date_columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce")
            if values.notna().any():
                dates = values.dt.strftime("%Y-%m-%d")
                return frame.loc[dates.eq(today)].copy()
    return frame.iloc[0:0].copy()


def build_master_data():
    """Snapshot today's data, keep six months, and persist master files."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _restore_if_missing(MASTER_STOCK, "outputs/MASTER_DAILY_STOCK_DATA.csv")
    _restore_if_missing(MASTER_TRADES, "outputs/MASTER_TRADES.csv")
    _restore_if_missing(MASTER_DAILY, "outputs/MASTER_DAILY_SUMMARY.csv")

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
        if "TradeDate" in stock.columns:
            stock = stock.drop(columns=["TradeDate"])
        stock.insert(0, "TradeDate", today)
        stock["DataSnapshotIST"] = datetime.now(IST).isoformat(timespec="seconds")
        _merge(MASTER_STOCK, stock, ["TradeDate", "Symbol"])

    if not trades.empty:
        t = trades.copy()
        if "TradeDate" in t.columns:
            t = t.drop(columns=["TradeDate"])
        date_col = next((c for c in ["entry_time", "exit_time", "timestamp"] if c in t.columns), None)
        t.insert(0, "TradeDate", t[date_col].astype(str).str[:10] if date_col else today)
        _merge(
            MASTER_TRADES,
            t,
            ["TradeDate", "symbol", "entry_time", "signal", "entry"] if "symbol" in t.columns else ["TradeDate"],
        )

    # Trade activity belongs to the entry day; realized P&L belongs to the exit day.
    today_trades = _today_rows(trades, ["entry_time", "timestamp", "exit_time"], today)
    today_closed = _today_rows(trades, ["exit_time"], today)
    today_signals = _today_rows(signals, ["timestamp", "entry_time"], today)
    today_pnl = float(pd.to_numeric(today_closed.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    row = {
        "TradeDate": today,
        "PreparedAtIST": datetime.now(IST).isoformat(timespec="seconds"),
        "StocksInGapBoard": int(len(gaps)),
        "GapUps": int((gaps.get("GapType", pd.Series(dtype=str)) == "GAP_UP").sum()),
        "GapDowns": int((gaps.get("GapType", pd.Series(dtype=str)) == "GAP_DOWN").sum()),
        "SignalsRecorded": int(len(today_signals)),
        "TradesRecorded": int(len(today_trades)),
        "ClosedTrades": int((today_closed.get("status", pd.Series(dtype=str)).astype(str).str.upper() == "CLOSED").sum()),
        "FinalSignals": int(diag.get("final_signals", 0) or 0),
        "StocksScanned": int(diag.get("stocks_scanned", 0) or 0),
        "LiquidityPassed": int(diag.get("liquidity_passed", 0) or 0),
        "OpeningSetupPassed": int(diag.get("opening_setup_passed", 0) or 0),
        "MarketAlignmentPassed": int(diag.get("market_alignment_passed", 0) or 0),
        "SectorAlignmentPassed": int(diag.get("sector_alignment_passed", 0) or 0),
        "StrategySetupPassed": int(diag.get("strategy_setup_passed", 0) or 0),
        "StockAlignmentPassed": int(diag.get("stock_alignment_passed", 0) or 0),
        "DailyPnL": round(today_pnl, 2),
    }
    _merge(MASTER_DAILY, pd.DataFrame([row]), ["TradeDate"])

    enforce_six_month_retention()

    for path in (MASTER_STOCK, MASTER_TRADES, MASTER_DAILY):
        try:
            sync(path, f"outputs/{path.name}", f"Update master trading data {today}")
        except Exception as error:
            print("Master data sync skipped:", error)

    return {"stock": str(MASTER_STOCK), "trades": str(MASTER_TRADES), "daily": str(MASTER_DAILY)}
