"""Candidate ranking helpers retained for compatibility with the test suite.

Gap magnitude is the primary priority metric. ATR is intentionally not used as
an independent priority signal here; callers may use it only as a secondary
tie-breaker after the gap magnitude.

This module is intentionally kept in the strategy package so clean checkouts
used by CI and Streamlit resolve the same import path.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def sort_key(candidate: dict) -> float:
    """Return the primary candidate priority: absolute gap percentage."""
    try:
        return abs(float(candidate.get("gap_percent", 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def metrics() -> dict:
    """Return the compatibility metadata expected by diagnostics/tests."""
    return {"metrics_calculated_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds")}
