"""
NIFTY LARGEMIDCAP 250 PULLBACK BREAKOUT TRADING BOT
===================================================

UNIVERSE
--------
NIFTY LargeMidcap 250 stocks

TIME RULES
----------
09:15 - Market opens / observation begins
09:45 - Trading and valid breakout entries begin
13:30 - Last new entry
15:00 - Mandatory square-off
15:30 - Market closes

SETUP
-----
5-minute candles = pullback structure
1-minute candle   = final breakout entry confirmation

BUY
---
1. Market bullish
2. Sector bullish
3. Stock bullish
4. Valid 5-minute pullback
5. Breakout must happen AFTER 09:45
6. Completed 1-minute candle must CLOSE above frozen high
7. Entry at breakout candle close
8. SL = pullback low
9. Target = 1:1

SELL
----
1. Market bearish
2. Sector bearish
3. Stock bearish
4. Valid 5-minute pullback
5. Breakdown must happen AFTER 09:45
6. Completed 1-minute candle must CLOSE below frozen low
7. Entry at breakdown candle close
8. SL = pullback high
9. Target = 1:1

All open positions are closed at 15:00.
"""


# ============================================================
# STOCK UNIVERSE
# ============================================================

STOCK_UNIVERSE = "NIFTY_LARGEMIDCAP_250"

MAX_STOCKS = 250


# ============================================================
# MARKET TIMES
# ============================================================

MARKET_OPEN = "09:15"

OBSERVATION_START = "09:15"

TRADING_START = "09:45"

LAST_ENTRY_TIME = "13:30"

SQUARE_OFF_TIME = "15:00"

MARKET_CLOSE = "15:30"


# ============================================================
# IMPORTANT TIME RULE
# ============================================================

# Price data from 09:15 onward can be used to build
# the day's structure/high/low.
#
# However, a breakout/breakdown that occurs BEFORE 09:45
# CANNOT trigger a trade.
#
# The final 1-minute breakout candle must close at or
# after TRADING_START.

REQUIRE_BREAKOUT_AFTER_TRADING_START = True

ALLOW_NEW_ENTRIES_AFTER_LAST_ENTRY = False

MANDATORY_SQUARE_OFF = True


# ============================================================
# TIMEFRAMES
# ============================================================

# Main setup / pullback structure

SETUP_TIMEFRAME = "5m"

PULLBACK_TIMEFRAME = "5m"


# Final entry trigger

ENTRY_TIMEFRAME = "1m"

ENTRY_CONFIRMATION_TIMEFRAME = "1m"


# ============================================================
# LONG / SHORT
# ============================================================

ENABLE_LONG = True

ENABLE_SHORT = True


# ============================================================
# ALIGNMENT RULE
# ============================================================

# BUY:
# Market = BULLISH
# Sector = BULLISH
# Stock  = BULLISH
#
# SELL:
# Market = BEARISH
# Sector = BEARISH
# Stock  = BEARISH

REQUIRE_MARKET_ALIGNMENT = True

REQUIRE_SECTOR_ALIGNMENT = True

REQUIRE_STOCK_ALIGNMENT = True


# ============================================================
# BREAKOUT LEVEL
# ============================================================

# Once a valid setup/pullback begins,
# the breakout reference high/low is frozen.
#
# BUY:
# 1-minute candle must CLOSE ABOVE frozen high.
#
# SELL:
# 1-minute candle must CLOSE BELOW frozen low.

FREEZE_BREAKOUT_LEVEL = True

REQUIRE_CANDLE_CLOSE_CONFIRMATION = True


# ============================================================
# PULLBACK
# ============================================================

# Pullback structure uses completed 5-minute candles.

MIN_PULLBACK_CANDLES = 2


# ============================================================
# ENTRY
# ============================================================

# Entry is taken only after the completed 1-minute candle
# confirms the breakout/breakdown.

ENTRY_METHOD = "ONE_MINUTE_CLOSE"

ENTRY_AT_CONFIRMATION_CLOSE = True


# ============================================================
# STOP LOSS
# ============================================================

# BUY:
# SL = lowest low of valid 5-minute pullback structure
#
# SELL:
# SL = highest high of valid 5-minute pullback structure

STOP_LOSS_METHOD = "PULLBACK_EXTREME"


# ============================================================
# TARGET
# ============================================================

# 1:1 Risk Reward
#
# BUY:
# Risk   = Entry - SL
# Target = Entry + Risk
#
# SELL:
# Risk   = SL - Entry
# Target = Entry - Risk

RISK_REWARD_RATIO = 1.0


# ============================================================
# CAPITAL / RISK
# ============================================================

TOTAL_CAPITAL = 250000

MAX_RISK_PER_TRADE = 1250

MIN_REQUIRED_RISK = 1240

RISK_PERCENT = 0.5


# ============================================================
# TRADE LIMITS
# ============================================================

MAX_TRADES_PER_STOCK = 1

# ============================================================
# POSITION MANAGEMENT
# ============================================================

# Maximum simultaneous open positions
MAX_OPEN_POSITIONS = 2

# ============================================================
# DAILY LIMITS
# ============================================================

# Stop trading after 3 full stop losses
DAILY_MAX_LOSS = 3750

# Stop taking new trades after reaching the target
DAILY_PROFIT_TARGET = 5000

# Wait after a stop loss before taking a new trade
COOLDOWN_MINUTES = 15

# ============================================================
# POSITION SIZING
# ============================================================

# Quantity is calculated automatically using:
# 1. Maximum risk per trade
# 2. Available capital
POSITION_SIZE_METHOD = "RISK_AND_CAPITAL"

# ============================================================
# TRADING MODE
# ============================================================

PAPER_TRADING = True

LIVE_TRADING = False


# ============================================================
# SCANNER
# ============================================================

SCAN_INTERVAL_SECONDS = 5


# ============================================================
# OUTPUT FILES
# ============================================================

TRADE_LOG_FILE = "outputs/trades.csv"

SIGNAL_LOG_FILE = "outputs/signals.csv"


# ============================================================
# SETTINGS TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 80)

    print(
        "NIFTY LARGEMIDCAP 250 "
        "PULLBACK BREAKOUT BOT SETTINGS"
    )

    print("=" * 80)

    print("Universe                :", STOCK_UNIVERSE)
    print("Maximum Stocks          :", MAX_STOCKS)

    print("-" * 80)

    print("Market Open             :", MARKET_OPEN)
    print("Observation Starts      :", OBSERVATION_START)
    print("Trading Starts          :", TRADING_START)
    print("Last New Entry          :", LAST_ENTRY_TIME)
    print("Mandatory Square Off    :", SQUARE_OFF_TIME)
    print("Market Close            :", MARKET_CLOSE)

    print("-" * 80)

    print("Setup Timeframe         :", SETUP_TIMEFRAME)
    print("Pullback Timeframe      :", PULLBACK_TIMEFRAME)
    print("Entry Timeframe         :", ENTRY_TIMEFRAME)

    print(
        "Minimum Pullback Candles:",
        MIN_PULLBACK_CANDLES
    )

    print(
        "Breakout After 09:45    :",
        REQUIRE_BREAKOUT_AFTER_TRADING_START
    )

    print(
        "1-Min Close Required    :",
        REQUIRE_CANDLE_CLOSE_CONFIRMATION
    )

    print("-" * 80)

    print(
        "Market Alignment        :",
        REQUIRE_MARKET_ALIGNMENT
    )

    print(
        "Sector Alignment        :",
        REQUIRE_SECTOR_ALIGNMENT
    )

    print(
        "Stock Alignment         :",
        REQUIRE_STOCK_ALIGNMENT
    )

    print("-" * 80)

    print(
        "Stop Loss               :",
        STOP_LOSS_METHOD
    )

    print(
        "Risk Reward             :",
        f"1:{RISK_REWARD_RATIO}"
    )

    print(
        "Maximum Risk / Trade    :",
        MAX_RISK_PER_TRADE
    )
    print(
        "Minimum Required Risk   :",
        MIN_REQUIRED_RISK
    )
    print(
        "Maximum Open Positions  :",
        MAX_OPEN_POSITIONS
    )

    print(
        "Daily Max Loss          :",
        DAILY_MAX_LOSS
    )

    print(
        "Daily Profit Target     :",
        DAILY_PROFIT_TARGET
    )

    print(
        "Cooldown (Minutes)      :",
        COOLDOWN_MINUTES
    )

    print(
        "Position Sizing         :",
        POSITION_SIZE_METHOD
    )

    print("-" * 80)

    print("Paper Trading           :", PAPER_TRADING)
    print("Live Trading            :", LIVE_TRADING)

    print("=" * 80)