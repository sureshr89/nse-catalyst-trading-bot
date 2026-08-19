"""Hard paper-trading limits shared by Strategy 1-5."""
CAPITAL_PER_TRADE = 250_000.0
STRATEGY_CAPITAL = CAPITAL_PER_TRADE
MIN_TRADE_RISK = 1_400.0
MAX_TRADE_RISK = 1_500.0
MAX_TRADES_PER_STRATEGY_PER_DAY = 1
MAX_DAILY_LOSS_PER_STRATEGY = 1_500.0
TARGET_R_MULTIPLE = 1.25
MARKET_REFRESH_SECONDS = 15
PAPER_TRADING_ONLY = True
SQUARE_OFF_HOUR = 15
SQUARE_OFF_MINUTE = 0

def can_open_trade(strategy: str, trade_count_today: int, realized_pnl_today: float) -> tuple[bool, str]:
    if trade_count_today >= MAX_TRADES_PER_STRATEGY_PER_DAY:
        return False, f"{strategy}: maximum 1 trade for today reached"
    if realized_pnl_today <= -MAX_DAILY_LOSS_PER_STRATEGY:
        return False, f"{strategy}: daily loss limit of ₹1,500 reached"
    return True, "OK"

def actual_risk(entry: float, sl: float, quantity: int) -> float:
    return abs(float(entry) - float(sl)) * int(quantity)

def quantity_for_risk(entry: float, sl: float, capital: float = CAPITAL_PER_TRADE) -> tuple[int, float]:
    entry = float(entry); sl = float(sl); capital = float(capital); risk_per_share = abs(entry - sl)
    if risk_per_share <= 0 or entry <= 0 or capital <= 0: return 0, 0.0
    max_qty_capital = int(capital // entry)
    min_qty = max(1, int((MIN_TRADE_RISK + risk_per_share - 1e-12) // risk_per_share))
    max_qty = min(max_qty_capital, int(MAX_TRADE_RISK // risk_per_share))
    if max_qty < min_qty: return 0, 0.0
    quantity = max_qty; risk = actual_risk(entry, sl, quantity)
    return (quantity, risk) if MIN_TRADE_RISK <= risk <= MAX_TRADE_RISK else (0, 0.0)

def target_price(entry: float, sl: float, side: str) -> float:
    risk_per_share = abs(float(entry) - float(sl))
    if side.upper() == "BUY": return float(entry) + TARGET_R_MULTIPLE * risk_per_share
    if side.upper() == "SELL": return float(entry) - TARGET_R_MULTIPLE * risk_per_share
    raise ValueError("side must be BUY or SELL")
