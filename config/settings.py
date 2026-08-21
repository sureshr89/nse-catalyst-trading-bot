"""Configuration for the five NIFTY 500 paper-trading strategies."""
import os
import time
os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

STOCK_UNIVERSE = "NIFTY_500"
MAX_STOCKS = 500
# Live constituent-data safety gate: 98% = 490 of 500 verified stocks.
# Collection itself is allowed to be partial during the 15-second window;
# this threshold controls market/trade readiness only.
MIN_DATA_COVERAGE_PCT = 98.0
MIN_DATA_COVERAGE_COUNT = int(MAX_STOCKS * MIN_DATA_COVERAGE_PCT / 100)
MARKET_OPEN = "09:15"
OBSERVATION_START = "09:15"
PREMARKET_PREP_TIME = "09:20"
TRADING_START = "09:45"
LAST_ENTRY_TIME = "14:00"
SQUARE_OFF_TIME = "15:00"
MARKET_CLOSE = "15:30"

# One common 15-second collection/decision cycle for all five strategies.
# Valid Dhan prices are merged during the window; the finalized snapshot is
# shared by AD, sectors, dashboard, stock selection and S1-S5.
SCAN_INTERVAL_SECONDS = 15
MARKET_DATA_REFRESH_SECONDS = 15
LIVE_COLLECTION_WINDOW_SECONDS = 15
LIVE_PRICE_MONITOR_SECONDS = 2

# Master market alignment — applies to every strategy.
REQUIRE_MARKET_ALIGNMENT = True
NIFTY500_MIN_CHANGE_PCT = 0.0
NIFTY500_AD_MIN = 1.0
SECTOR_MIN_CHANGE_PCT = 0.0
REQUIRE_STOCK_ALIGNMENT = False

ENTRY_TIMEFRAME = "LIVE_LTP"
ENTRY_CONFIRMATION_TIMEFRAME = "PREVIOUS_COMPLETED_CANDLE"
BUY_PREVIOUS_CANDLE = "GREEN"
SELL_PREVIOUS_CANDLE = "RED"

ALLOCATED_CAPITAL_PER_TRADE = 250000
MIN_REQUIRED_RISK = 1400
MAX_RISK_PER_TRADE = 1500
RISK_REWARD_RATIO = 1.25
MIN_RR_RATIO = 1.25
POSITION_SIZE_METHOD = "RISK_BOUNDED_BY_SL"

TOTAL_CAPITAL = 1250000
MAX_OPEN_POSITIONS = 5
MAX_TRADES_PER_STRATEGY_PER_DAY = 1
DAILY_MAX_LOSS_PER_STRATEGY = 1500
MAX_TRADES_PER_STOCK = 1
DAILY_MAX_LOSS = DAILY_MAX_LOSS_PER_STRATEGY
COOLDOWN_MINUTES = 0

PAPER_TRADING = True
LIVE_TRADING = False

STRATEGY_NAME = "NIFTY_500_OHLC_PDH_PDL_S1_S5"
STOP_LOSS_METHOD = "STRATEGY_SPECIFIC_ENTRY_TIME_ONLY"
MASTER_JOURNAL_FILE = "outputs/strategy_journal_master.csv"
SIGNAL_LOG_FILE = "outputs/signals.csv"
TRADE_LOG_FILE = "outputs/trades.csv"
DAILY_PROFIT_TARGET = None
