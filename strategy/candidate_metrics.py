"""Candidate ranking metrics for the NIFTY 500 paper strategy.

Priority rule:
1. Larger opening gap versus PDH/PDL first.
2. Higher ATR% second.

These metrics rank candidates only after the complete price-action setup has
qualified; they do not create a trade by themselves.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _clean(df):
    if df is None or df.empty or "Datetime" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["Datetime"] = pd.to_datetime(out["Datetime"], errors="coerce")
    try:
        if out["Datetime"].dt.tz is None:
            out["Datetime"] = out["Datetime"].dt.tz_localize(INDIA_TZ)
        else:
            out["Datetime"] = out["Datetime"].dt.tz_convert(INDIA_TZ)
    except Exception:
        return pd.DataFrame()
    for c in ["Open", "High", "Low", "Close"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["Datetime", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)


def atr_pct(intraday, period=14):
    """Return ATR as a percentage of the latest close using completed 1-minute candles."""
    d = _clean(intraday)
    if len(d) < period + 1 or not {"High", "Low", "Close"}.issubset(d.columns):
        return 0.0
    previous = d["Close"].shift(1)
    true_range = pd.concat([
        (d["High"] - d["Low"]).abs(),
        (d["High"] - previous).abs(),
        (d["Low"] - previous).abs(),
    ], axis=1).max(axis=1)
    atr = float(true_range.tail(period).mean())
    close = float(d.iloc[-1]["Close"])
    return round((atr / close) * 100.0, 4) if close > 0 else 0.0


def metrics(price_data, symbol, intraday):
    """Calculate the secondary movement metric used after gap qualification."""
    return {
        "atr_pct": atr_pct(intraday),
        "metrics_calculated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds"),
    }


def gap_priority_pct(row):
    """Return opening-gap magnitude; larger gaps always receive higher priority."""
    try:
        return abs(float(row.get("gap_percent", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def sort_key(row):
    """Primary: larger gap. Secondary: higher ATR%."""
    return (gap_priority_pct(row), float(row.get("atr_pct", 0) or 0))
