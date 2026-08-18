"""Single source of truth for user-facing strategy definitions and versions."""

STRATEGY_VERSION = "2026.08.18.v3"
STRATEGY_1_NAME = "PDH/PDL + Open Return"
STRATEGY_2_NAME = "Gap Extension Reversal"

STRATEGY_1_RULES = (
    ("BUY", "Today's Open > PDH → live LTP first reaches/crosses PDH from above? → live LTP returns to/above Today's Open"),
    ("SELL", "Today's Open < PDL → live LTP first reaches/crosses PDL from below? → live LTP returns to/below Today's Open"),
    ("Market filter", "NIFTY 500 must meet the configured BUY/SELL threshold"),
    ("Entry", "Immediate current LTP when the return-to-Open condition is reached; no candle-close confirmation"),
    ("Stop loss", "BUY = PDH • SELL = PDL"),
    ("Target", "Default 1.25R from the actual live entry"),
)

STRATEGY_2_RULES = (
    ("SELL", "Today's Open > PDH → live price extends above Open → live LTP crosses below Open"),
    ("BUY", "Today's Open < PDL → live price extends below Open → live LTP crosses above Open"),
    ("Market filter", "NIFTY 500 is a soft protective filter; strong opposite movement blocks the setup"),
    ("Entry", "Immediate current LTP when the live trigger is reached; no candle-close confirmation"),
    ("Stop loss", "SELL = trigger-day high • BUY = trigger-day low"),
    ("Target", "PDH for SELL • PDL for BUY, subject to minimum 1.25R"),
)


def strategy_metadata(strategy: str) -> dict:
    key = str(strategy).upper().strip()
    if key in {"STRATEGY_1", "S1", "OPEN_RETURN"}:
        return {"strategy": "STRATEGY_1", "name": STRATEGY_1_NAME, "version": STRATEGY_VERSION, "rules": STRATEGY_1_RULES}
    if key in {"STRATEGY_2", "S2", "GAP_EXTENSION_REVERSAL"}:
        return {"strategy": "STRATEGY_2", "name": STRATEGY_2_NAME, "version": STRATEGY_VERSION, "rules": STRATEGY_2_RULES}
    raise ValueError(f"Unknown strategy: {strategy}")
