"""Candidate ordering for the NIFTY 500 paper strategy.

There is only one candidate-priority metric:
1. Largest qualifying opening-gap magnitude first.

ATR is intentionally removed from candidate ranking and entry selection.
Risk is handled separately by the risk engine and position sizing.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def gap_priority_pct(row):
    """Return absolute qualifying gap percentage; larger gaps rank first."""
    try:
        return abs(float(row.get("gap_percent", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def metrics(price_data=None, symbol=None, intraday=None):
    """Return non-ranking metadata. ATR is deliberately not calculated."""
    return {"metrics_calculated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds")}


def sort_key(row):
    """Only candidate priority: largest absolute qualifying gap."""
    return gap_priority_pct(row)
