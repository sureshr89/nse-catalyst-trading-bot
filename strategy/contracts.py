"""Single source of truth for the clean Dhan-only S1-S5 strategy contract."""
from config.settings import (
    ALLOCATED_CAPITAL_PER_TRADE,
    DAILY_MAX_LOSS_PER_STRATEGY,
    MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK,
    MIN_RR_RATIO,
    MAX_TRADES_PER_STRATEGY_PER_DAY,
    SQUARE_OFF_TIME,
    STOCK_UNIVERSE,
    MIN_DATA_COVERAGE_PCT,
)

STRATEGY_VERSION = "2026.08.21.clean-dhan-v2"
STRATEGY_1_NAME = "PDH/PDL Sweep + Open Reclaim"
STRATEGY_2_NAME = "PDH/PDL Breakout + Retest"
STRATEGY_3_NAME = "Opposite PDH/PDL Sweep + Open Reversal"
STRATEGY_4_NAME = "Intraday High/Low Breakout"
STRATEGY_5_NAME = "Direct PDH/PDL Breakout"

COMMON_RULES = (
    ("Universe", STOCK_UNIVERSE),
    ("Live source", "Dhan only; no Yahoo or legacy strategy source"),
    ("BUY market filter", "NIFTY 500 change > 0% AND A/D ratio > 1 AND positive sectors > negative sectors"),
    ("SELL market filter", "NIFTY 500 change < 0% AND A/D ratio < 1 AND negative sectors > positive sectors"),
    ("Coverage", f"At least {MIN_DATA_COVERAGE_PCT:.0f}% verified NIFTY 500 quotes and sector-priced constituents ({int(MIN_DATA_COVERAGE_PCT)}% gate)"),
    ("Data", "Dhan live OHLC/LTP + Dhan PDH/PDL/PDC + completed Dhan 1-minute candles where the strategy requires them"),
    ("Previous candle", "Diagnostic only; never an entry gate for S1-S5"),
    ("Indicators", "Not used for S1-S5 entry"),
    ("Entry", "Live LTP trigger; no current-candle close confirmation"),
    ("Capital allocation", f"₹{ALLOCATED_CAPITAL_PER_TRADE:,.0f} per trade"),
    ("Max trades", f"Maximum {MAX_TRADES_PER_STRATEGY_PER_DAY} trade per strategy per day"),
    ("Daily loss limit", f"Maximum ₹{DAILY_MAX_LOSS_PER_STRATEGY:,.0f} loss per strategy per day"),
    ("Target", f"{MIN_RR_RATIO:.2f}R"),
    ("Position risk", f"Actual risk ₹{MIN_REQUIRED_RISK:,.0f}–₹{MAX_RISK_PER_TRADE:,.0f}; otherwise no trade"),
    ("Exit", f"SL or {MIN_RR_RATIO:.2f}R target; mandatory {SQUARE_OFF_TIME} IST paper square-off"),
    ("Execution", "PAPER TRADING ONLY"),
    ("Look-ahead rule", "Only completed candles and current Dhan LTP/quote data available at evaluation time"),
)

STRATEGY_RULES = {
    "S1": (
        ("BUY", "Open > PDH → day Low <= PDH → live LTP > Today's Open → BUY"),
        ("SELL", "Open < PDL → day High >= PDL → live LTP < Today's Open → SELL"),
        ("SL", "BUY = PDH • SELL = PDL"),
    ),
    "S2": (
        ("BUY", "Completed candle history shows break above PDH → pullback to PDH → live LTP >= PDH → BUY"),
        ("SELL", "Completed candle history shows break below PDL → pullback to PDL → live LTP <= PDL → SELL"),
        ("SL", "BUY = pullback Low • SELL = pullback High"),
    ),
    "S3": (
        ("BUY", "Open inside PDH/PDL → day Low <= PDL → live LTP > Today's Open → BUY"),
        ("SELL", "Open inside PDH/PDL → day High >= PDH → live LTP < Today's Open → SELL"),
        ("SL", "BUY = Today's Low • SELL = Today's High"),
    ),
    "S4": (
        ("BUY", "Live LTP breaks previously completed intraday High → BUY"),
        ("SELL", "Live LTP breaks previously completed intraday Low → SELL"),
        ("SL", "BUY = previous intraday Low • SELL = previous intraday High"),
    ),
    "S5": (
        ("BUY", "Live LTP > PDH → BUY"),
        ("SELL", "Live LTP < PDL → SELL"),
        ("SL", "BUY = PDH • SELL = PDL"),
    ),
}


def strategy_metadata(strategy: str) -> dict:
    canonical = str(strategy).upper().strip()
    if canonical not in STRATEGY_RULES:
        raise ValueError(f"Unknown strategy: {strategy}")
    names = {
        "S1": STRATEGY_1_NAME,
        "S2": STRATEGY_2_NAME,
        "S3": STRATEGY_3_NAME,
        "S4": STRATEGY_4_NAME,
        "S5": STRATEGY_5_NAME,
    }
    return {"strategy": canonical, "name": names[canonical], "version": STRATEGY_VERSION, "rules": COMMON_RULES + STRATEGY_RULES[canonical]}
