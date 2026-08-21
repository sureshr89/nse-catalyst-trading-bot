"""Canonical hard risk limits shared by S1-S5 paper trading.

Keep strategy/session timing in :mod:`config.trading_rules` and general
runtime/universe settings in :mod:`config.settings`.  This module is the
single source of truth for position sizing and monetary risk limits.
"""

CAPITAL_PER_TRADE = 250_000.0
STRATEGY_CAPITAL = CAPITAL_PER_TRADE
MIN_TRADE_RISK = 1_400.0
MAX_TRADE_RISK = 1_500.0
TARGET_R_MULTIPLE = 1.25
MAX_TRADES_PER_STRATEGY_PER_DAY = 1
MAX_DAILY_LOSS_PER_STRATEGY = 1_500.0

# Legacy/shared aliases kept for compatibility with existing callers.
PAPER_TRADING_ONLY = True
MARKET_REFRESH_SECONDS = 15
SQUARE_OFF_HOUR = 15
SQUARE_OFF_MINUTE = 0


def can_open_trade(strategy: str, trade_count_today: int, realized_pnl_today: float) -> tuple[bool, str]:
    """Return whether a strategy may open another paper trade today."""
    name = str(strategy).upper().strip() or "STRATEGY"
    if int(trade_count_today) >= MAX_TRADES_PER_STRATEGY_PER_DAY:
        return False, f"{name}: maximum {MAX_TRADES_PER_STRATEGY_PER_DAY} trade for today reached"
    if float(realized_pnl_today) <= -MAX_DAILY_LOSS_PER_STRATEGY:
        return False, f"{name}: daily loss limit of ₹{MAX_DAILY_LOSS_PER_STRATEGY:,.0f} reached"
    return True, "OK"


def actual_risk(entry: float, sl: float, quantity: int) -> float:
    """Absolute rupee risk for the requested quantity."""
    return abs(float(entry) - float(sl)) * int(quantity)


def quantity_for_risk(
    entry: float,
    sl: float,
    capital: float = CAPITAL_PER_TRADE,
) -> tuple[int, float]:
    """Find the largest quantity that stays inside capital and risk bounds.

    A trade is rejected when no whole-share quantity can satisfy both the
    minimum and maximum risk limits. This avoids silently under-risking a trade.
    """
    entry = float(entry)
    sl = float(sl)
    capital = float(capital)
    risk_per_share = abs(entry - sl)
    if entry <= 0 or capital <= 0 or risk_per_share <= 0:
        return 0, 0.0

    max_qty_capital = int(capital // entry)
    min_qty = max(1, int((MIN_TRADE_RISK + risk_per_share - 1e-12) // risk_per_share))
    max_qty = min(max_qty_capital, int(MAX_TRADE_RISK // risk_per_share))
    if max_qty < min_qty:
        return 0, 0.0

    quantity = max_qty
    risk = actual_risk(entry, sl, quantity)
    if MIN_TRADE_RISK <= risk <= MAX_TRADE_RISK:
        return quantity, risk
    return 0, 0.0


def target_price(entry: float, sl: float, side: str) -> float:
    """Return the 1.25R target on the correct side of the entry."""
    risk_per_share = abs(float(entry) - float(sl))
    direction = str(side).upper().strip()
    if risk_per_share <= 0:
        raise ValueError("entry and stop_loss must be different")
    if direction == "BUY":
        return float(entry) + TARGET_R_MULTIPLE * risk_per_share
    if direction == "SELL":
        return float(entry) - TARGET_R_MULTIPLE * risk_per_share
    raise ValueError("side must be BUY or SELL")
