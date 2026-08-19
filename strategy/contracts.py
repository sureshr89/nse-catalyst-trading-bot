"""Single source of truth for the five NIFTY 500 price-action strategies."""

STRATEGY_VERSION = "2026.08.19.v3"
STRATEGY_1_NAME = "PDH/PDL Sweep + Open Reclaim"
STRATEGY_2_NAME = "PDH/PDL Breakout + Retest"
STRATEGY_3_NAME = "PDL/PDH Sweep + Open Reclaim"
STRATEGY_4_NAME = "Intraday High/Low Breakout"
STRATEGY_5_NAME = "Direct PDH/PDL Breakout"

COMMON_RULES = (
    ("Universe", "NIFTY 500"),
    ("BUY market filter", "NIFTY 500 change > 0% AND sector alignment > 0% AND NIFTY 500 A/D ratio > 1"),
    ("SELL market filter", "NIFTY 500 change < 0% AND sector alignment < 0% AND NIFTY 500 A/D ratio < 1"),
    ("Data", "Today's OHLC + live LTP + PDH/PDL + already-formed intraday levels"),
    ("Previous candle", "BUY requires previous completed candle GREEN; SELL requires previous completed candle RED"),
    ("Sector analysis", "Used only as the common market-alignment gate"),
    ("Indicators", "Not used for strategy entry"),
    ("Refresh", "Live data/strategy evaluation every 15 seconds"),
    ("Entry", "Live LTP trigger; no current-candle close confirmation"),
    ("Capital allocation", "₹2,50,000 per trade"),
    ("Max trades", "Maximum 2 trades per strategy per day"),
    ("Daily loss limit", "Maximum ₹3,000 loss per strategy per day; lock strategy after limit"),
    ("Target", "1.25R"),
    ("Position risk", "Actual risk must be ₹1,400–₹1,500 from the calculated SL distance; otherwise no trade"),
    ("Position sizing", "Quantity is calculated from Entry-to-SL distance; capital per trade capped at ₹2,50,000"),
    ("Exit", "SL or 1.25R target; mandatory 15:00 IST paper square-off"),
    ("Execution", "PAPER TRADING ONLY; no live order placement"),
    ("Look-ahead rule", "Only OHLC/levels available before or at entry may be used"),
)

STRATEGY_RULES = {
    "S1": (
        ("BUY", "Open > PDH → Low < PDH → live LTP returns to Today's Open → BUY"),
        ("SELL", "Open < PDL → High > PDL → live LTP returns to Today's Open → SELL"),
        ("SL", "BUY = Today's Low at entry • SELL = Today's High at entry"),
    ),
    "S2": (
        ("BUY", "Live price breaks PDH → pulls back to PDH → holds/reclaims PDH → BUY"),
        ("SELL", "Live price breaks PDL → pulls back to PDL → holds/fails below PDL → SELL"),
        ("SL", "BUY = retest pullback Low • SELL = retest pullback High"),
    ),
    "S3": (
        ("BUY", "Open > PDL → Low < PDL → live LTP returns to Today's Open → BUY"),
        ("SELL", "Open < PDH → High > PDH → live LTP returns below Today's Open → SELL"),
        ("SL", "BUY = Today's Low at entry • SELL = Today's High at entry"),
    ),
    "S4": (
        ("BUY", "Live LTP breaks the previously formed intraday High → BUY"),
        ("SELL", "Live LTP breaks the previously formed intraday Low → SELL"),
        ("SL", "BUY = previous intraday Low • SELL = previous intraday High"),
    ),
    "S5": (
        ("BUY", "Live LTP breaks above PDH → BUY"),
        ("SELL", "Live LTP breaks below PDL → SELL"),
        ("SL", "BUY = PDH • SELL = PDL"),
    ),
}


def strategy_metadata(strategy: str) -> dict:
    key = str(strategy).upper().strip()
    names = {
        "S1": STRATEGY_1_NAME, "STRATEGY_1": STRATEGY_1_NAME, "OPEN_RETURN": STRATEGY_1_NAME,
        "S2": STRATEGY_2_NAME, "STRATEGY_2": STRATEGY_2_NAME,
        "S3": STRATEGY_3_NAME, "STRATEGY_3": STRATEGY_3_NAME,
        "S4": STRATEGY_4_NAME, "STRATEGY_4": STRATEGY_4_NAME,
        "S5": STRATEGY_5_NAME, "STRATEGY_5": STRATEGY_5_NAME,
    }
    canonical = key if key in {"S1", "S2", "S3", "S4", "S5"} else {
        "STRATEGY_1": "S1", "OPEN_RETURN": "S1", "STRATEGY_2": "S2",
        "STRATEGY_3": "S3", "STRATEGY_4": "S4", "STRATEGY_5": "S5",
    }.get(key)
    if canonical is None:
        raise ValueError(f"Unknown strategy: {strategy}")
    return {"strategy": canonical, "name": names[canonical], "version": STRATEGY_VERSION, "rules": COMMON_RULES + STRATEGY_RULES[canonical]}
