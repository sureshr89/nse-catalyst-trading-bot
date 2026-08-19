"""Master trading limits shared by Strategy 1-5."""

STRATEGY_CAPITAL = 150_000.0
MIN_TRADE_RISK = 1_400.0
MAX_TRADE_RISK = 1_500.0
MAX_TRADES_PER_STRATEGY_PER_DAY = 2
MAX_DAILY_LOSS_PER_STRATEGY = 3_000.0
TARGET_R_MULTIPLE = 1.25
MARKET_REFRESH_SECONDS = 15


def can_open_trade(strategy: str, trade_count_today: int, realized_pnl_today: float) -> tuple[bool, str]:
    """Hard gate before any new trade is opened."""
    if trade_count_today >= MAX_TRADES_PER_STRATEGY_PER_DAY:
        return False, f"{strategy}: maximum 2 trades for today reached"
    if realized_pnl_today <= -MAX_DAILY_LOSS_PER_STRATEGY:
        return False, f"{strategy}: daily loss limit of ₹3,000 reached"
    return True, "OK"


def actual_risk(entry: float, sl: float, quantity: int) -> float:
    """Return rupee risk from the actual entry/SL distance."""
    return abs(entry - sl) * quantity


def target_price(entry: float, sl: float, side: str) -> float:
    """Return a 1.25R target from entry and the actual SL."""
    risk_per_share = abs(entry - sl)
    if side.upper() == "BUY":
        return entry + TARGET_R_MULTIPLE * risk_per_share
    if side.upper() == "SELL":
        return entry - TARGET_R_MULTIPLE * risk_per_share
    raise ValueError("side must be BUY or SELL")
