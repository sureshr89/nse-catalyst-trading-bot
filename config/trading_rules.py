"""Single source of truth for paper-trading session/risk rules."""
from datetime import time

TRADING_START = time(9, 45)
LAST_ENTRY_TIME = time(14, 0)
SQUARE_OFF_TIME = time(15, 0)
REFRESH_SECONDS = 15
CAPITAL_PER_STRATEGY = 250_000
RISK_MIN = 1_400
RISK_MAX = 1_500
TARGET_RR = 1.25
MAX_TRADES_PER_STRATEGY_DAY = 1


def entry_allowed(now):
    t = now.time() if hasattr(now, "time") else now
    return TRADING_START <= t <= LAST_ENTRY_TIME


def force_square_off(now):
    t = now.time() if hasattr(now, "time") else now
    return t >= SQUARE_OFF_TIME
