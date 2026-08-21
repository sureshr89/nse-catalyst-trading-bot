"""Canonical runtime configuration for the five NIFTY 500 paper strategies."""
import os
import time

os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

# ---------------------------------------------------------------------------
# Universe and market session
# ---------------------------------------------------------------------------
STOCK_UNIVERSE = "NIFTY_500"
MAX_STOCKS = 500
MIN_DATA_COVERAGE_PCT = 98.0
MIN_DATA_COVERAGE_COUNT = int(MAX_STOCKS * MIN_DATA_COVERAGE_PCT / 100)
MARKET_OPEN = "09:15"
OBSERVATION_START = "09:15"
PREMARKET_PREP_TIME = "09:20"
TRADING_START = "09:45"
LAST_ENTRY_TIME = "14:00"
SQUARE_OFF_TIME = "15:00"
MARKET_CLOSE = "15:30"

# ---------------------------------------------------------------------------
# Fresh-data cycle
# ---------------------------------------------------------------------------
# Every cycle begins from a new full-universe request. Only current-cycle
# quotes count toward the 98% safety gate; stale quotes must not be reused.
COLLECTION_WINDOW_SECONDS = 15
DECISION_WINDOW_SECONDS = 10
SCAN_INTERVAL_SECONDS = COLLECTION_WINDOW_SECONDS + DECISION_WINDOW_SECONDS
MARKET_DATA_REFRESH_SECONDS = SCAN_INTERVAL_SECONDS
LIVE_COLLECTION_WINDOW_SECONDS = COLLECTION_WINDOW_SECONDS
LIVE_PRICE_MONITOR_SECONDS = 2

# News is deliberately outside the 15-second market-data gate. It only ranks
# already-eligible sector candidates and cannot make an incomplete market
# snapshot tradeable.
NEWS_CACHE_SECONDS = 180
NEWS_MAX_BATCH_SYMBOLS = 10
NEWS_MAX_BATCHES_PER_REFRESH = 8

# ---------------------------------------------------------------------------
# Master market alignment
# ---------------------------------------------------------------------------
# Final direction is deliberately strict: NIFTY 500 sign + breadth + sector
# majority must agree before any S1-S5 setup can become a trade signal.
REQUIRE_MARKET_ALIGNMENT = True
NIFTY500_MIN_CHANGE_PCT = 0.0
NIFTY500_AD_MIN = 1.0
SECTOR_MIN_CHANGE_PCT = 0.0
REQUIRE_STOCK_ALIGNMENT = False

ENTRY_TIMEFRAME = "LIVE_LTP"
ENTRY_CONFIRMATION_TIMEFRAME = "PREVIOUS_COMPLETED_CANDLE"
BUY_PREVIOUS_CANDLE = "GREEN"
SELL_PREVIOUS_CANDLE = "RED"

# ---------------------------------------------------------------------------
# Canonical risk settings
# ---------------------------------------------------------------------------
# Keep these names for existing imports. The executable sizing helpers live in
# config.trading_limits so there is one implementation of risk arithmetic.
ALLOCATED_CAPITAL_PER_TRADE = 250_000
MIN_REQUIRED_RISK = 1_400
MAX_RISK_PER_TRADE = 1_500
RISK_REWARD_RATIO = 1.25
MIN_RR_RATIO = 1.25
POSITION_SIZE_METHOD = "RISK_BOUNDED_BY_SL"

TOTAL_CAPITAL = 1_250_000
MAX_OPEN_POSITIONS = 5
MAX_TRADES_PER_STRATEGY_PER_DAY = 1
DAILY_MAX_LOSS_PER_STRATEGY = 1_500
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
