"""Hard paper-trading limits shared by Strategy 1-5."""

STRATEGY_CAPITAL = 250_000.0
MIN_TRADE_RISK = 1_400.0
MAX_TRADE_RISK = 1_500.0
MAX_TRADES_PER_STRATEGY_PER_DAY = 2
MAX_DAILY_LOSS_PER_STRATEGY = 3_000.0
TARGET_R_MULTIPLE = 1.25
MARKET_REFRESH_SECONDS = 15
PAPER_TRADING_ONLY = True
SQUARE_OFF_HOUR = 15
SQUARE_OFF_MINUTE = 0


def can_open_trade(strategy: str, trade_count_today: int, realized_pnl_today: float) -> tuple[bool, str]:
    """Hard gate before any new paper trade is opened."""
    if trade_count_today >= MAX_TRADES_PER_STRATEGY_PER_DAY:
        return False, f"{strategy}: maximum 2 trades for today reached"
    if realized_pnl_today <= -MAX_DAILY_LOSS_PER_STRATEGY:
        return False, f"{strategy}: daily loss limit of ₹3,000 reached"
    return True, "OK"


def actual_risk(entry: float, sl: float, quantity: int) -> float:
    """Return rupee risk from the actual entry/SL distance."""
    return abs(float(entry) - float(sl)) * int(quantity)


def quantity_for_risk(entry: float, sl: float, capital: float = STRATEGY_CAPITAL) -> tuple[int, float]:
    """Choose the largest whole quantity whose actual risk is ₹1,400–₹1,500 and capital stays within ₹2.5 lakh.

    If no integer quantity can satisfy the risk band, return (0, 0.0) and reject the trade.
    """
    entry = float(entry); sl = float(sl); capital = float(capital)
    risk_per_share = abs(entry - sl)
    if risk_per_share <= 0 or entry <= 0 or capital <= 0:
        return 0, 0.0
    max_qty_capital = int(capital // entry)
    if max_qty_capital < 1:
        return 0, 0.0
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
    """Return a 1.25R target from entry and the actual SL."""
    risk_per_share = abs(float(entry) - float(sl))
    if side.upper() == "BUY":
        return float(entry) + TARGET_R_MULTIPLE * risk_per_share
    if side.upper() == "SELL":
        return float(entry) - TARGET_R_MULTIPLE * risk_per_share
    raise ValueError("side must be BUY or SELL")
