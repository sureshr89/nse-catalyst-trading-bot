"""Canonical S1-S5 market-session rules.

Use this module for clock/session decisions only. Monetary risk and position
sizing live in :mod:`config.trading_limits`, while runtime/universe settings
live in :mod:`config.settings`.
"""
from datetime import time

TRADING_START = time(9, 45)
LAST_ENTRY_TIME = time(14, 0)
SQUARE_OFF_TIME = time(15, 0)
REFRESH_SECONDS = 15

# Compatibility aliases used by existing callers.
CAPITAL_PER_STRATEGY = 250_000
RISK_MIN = 1_400
RISK_MAX = 1_500
TARGET_RR = 1.25
MAX_TRADES_PER_STRATEGY_DAY = 1


def _as_time(value):
    """Normalize a datetime/time-like value to a datetime.time object."""
    if hasattr(value, "time"):
        return value.time()
    if isinstance(value, time):
        return value
    raise TypeError("now must be a datetime or datetime.time")


def entry_allowed(now):
    """Return True only during the configured entry window, inclusive."""
    t = _as_time(now)
    return TRADING_START <= t <= LAST_ENTRY_TIME


def force_square_off(now):
    """Return True from the configured square-off time onward."""
    return _as_time(now) >= SQUARE_OFF_TIME
