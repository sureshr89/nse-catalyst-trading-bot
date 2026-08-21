"""Small, deterministic candidate-ranking helpers retained for compatibility.

The clean S1-S5 strategy does not use ATR/indicators as entry signals. Gap
magnitude can be used only to prioritize inspection; it must never override
the canonical market gate or strategy setup.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo


def sort_key(candidate: dict) -> float:
    """Return absolute gap percentage for deterministic candidate ordering."""
    try:
        value = float(candidate.get("gap_percent", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return abs(value) if isfinite(value) else 0.0


def metrics() -> dict:
    """Return diagnostics metadata; no trading signal is derived here."""
    return {
        "metrics_calculated_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
        "priority_metric": "absolute_gap_percent",
        "used_as_entry_signal": False,
    }
