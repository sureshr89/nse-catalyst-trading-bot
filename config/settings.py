"""Configuration for the five NIFTY 500 paper-trading strategies."""
import os
import time
os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

STOCK_UNIVERSE = "NIFTY_500"
MAX_STOCKS = 500
MARKET_OPEN = "09:15"
OBSERVATION_START = "09:15"
PREMARKET_PREP_TIME = "09:20"
TRADING_START = "09:45"
LAST_ENTRY_TIME = "14:00"
SQUARE_OFF_TIME = "15:00"
MARKET_CLOSE = "15:30"

# One common market-data cycle for all five strategies.
SCAN_INTERVAL_SECONDS = 15
MARKET_DATA_REFRESH_SECONDS = 15
LIVE_PRICE_MONITOR_SECONDS = 2

# Master market alignment — applies to every strategy.
REQUIRE_MARKET_ALIGNMENT = True
NIFTY500_MIN_CHANGE_PCT = 0.0
NIFTY500_AD_MIN = 1.0
SECTOR_MIN_CHANGE_PCT = 0.0
REQUIRE_STOCK_ALIGNMENT = False

# Previous completed candle confirmation.
ENTRY_TIMEFRAME = "LIVE_LTP"
ENTRY_CONFIRMATION_TIMEFRAME = "PREVIOUS_COMPLETED_CANDLE"
BUY_PREVIOUS_CANDLE = "GREEN"
SELL_PREVIOUS_CANDLE = "RED"

# Position sizing is based on the actual entry-to-SL distance.
# Each trade is allocated up to Rs 2.5 lakh of capital.
ALLOCATED_CAPITAL_PER_TRADE = 250000
MIN_REQUIRED_RISK = 1400
MAX_RISK_PER_TRADE = 1500
RISK_REWARD_RATIO = 1.25
MIN_RR_RATIO = 1.25
POSITION_SIZE_METHOD = "RISK_BOUNDED_BY_SL"

# Five strategies × one active position per strategy = Rs 12.5 lakh maximum simultaneous paper capital.
TOTAL_CAPITAL = 1250000
MAX_OPEN_POSITIONS = 5

# Daily controls are per strategy, not global.
MAX_TRADES_PER_STRATEGY_PER_DAY = 1
DAILY_MAX_LOSS_PER_STRATEGY = 1500
MAX_TRADES_PER_STOCK = 1

# Compatibility aliases used by older risk/worker code.
DAILY_MAX_LOSS = DAILY_MAX_LOSS_PER_STRATEGY
COOLDOWN_MINUTES = 0

# Paper trading only. Dhan is now the primary market-data source when its
# Streamlit secrets are configured. No Dhan order endpoint is called.
PAPER_TRADING = True
LIVE_TRADING = False

STRATEGY_NAME = "NIFTY_500_OHLC_PDH_PDL_S1_S5"
STOP_LOSS_METHOD = "STRATEGY_SPECIFIC_ENTRY_TIME_ONLY"

# Single master journal for all strategies.
MASTER_JOURNAL_FILE = "outputs/strategy_journal_master.csv"
SIGNAL_LOG_FILE = "outputs/signals.csv"
TRADE_LOG_FILE = "outputs/trades.csv"

# Retired control kept only for backward-compatible imports.
DAILY_PROFIT_TARGET = None
