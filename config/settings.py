"""NIFTY 100 Gap-Failure + Open-Reclaim paper trading strategy."""

# All bot time comparisons use India Standard Time (IST), even when the
# hosting environment itself is configured for UTC.
import os
import time

os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

STOCK_UNIVERSE = "NIFTY_100"
MAX_STOCKS = 100
MARKET_OPEN = "09:15"
OBSERVATION_START = "09:15"
TRADING_START = "09:45"
LAST_ENTRY_TIME = "14:00"
SQUARE_OFF_TIME = "15:00"
MARKET_CLOSE = "15:30"

REQUIRE_MARKET_ALIGNMENT = True
REQUIRE_SECTOR_ALIGNMENT = True
REQUIRE_STOCK_ALIGNMENT = True
ENABLE_LONG = True
ENABLE_SHORT = True

STRATEGY_NAME = "GAP_FAILURE_OPEN_RECLAIM"
ENTRY_TIMEFRAME = "1m"
ENTRY_CONFIRMATION_TIMEFRAME = "1m"
STOP_LOSS_METHOD = "TODAY_LOW_HIGH"
RISK_REWARD_RATIO = 1.5
MIN_RR_RATIO = 1.5

TOTAL_CAPITAL = 250000
MAX_RISK_PER_TRADE = 1500
# Do not accept a tiny fraction of the risk budget. The actual risk must be
# at least 90% of ₹1,500 (₹1,350) and must never exceed ₹1,500.
MIN_REQUIRED_RISK = 1350
RISK_PERCENT = 0.6

MAX_TRADES_PER_STOCK = 1
MAX_OPEN_POSITIONS = 2
DAILY_MAX_LOSS = 3750
DAILY_PROFIT_TARGET = 5000
COOLDOWN_MINUTES = 15
POSITION_SIZE_METHOD = "RISK_AND_CAPITAL"
PAPER_TRADING = True
LIVE_TRADING = False
SCAN_INTERVAL_SECONDS = 30

TRADE_LOG_FILE = "outputs/trades.csv"
SIGNAL_LOG_FILE = "outputs/signals.csv"
