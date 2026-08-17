"""Single source of truth for user-facing strategy definitions and versions.

Runtime engines remain authoritative for calculations; this module prevents
Streamlit pages and reports from maintaining a second, stale copy of the rules.
"""

STRATEGY_VERSION = "2026.08.18.v1"
STRATEGY_1_NAME = "PDH/PDL + Open Return"
STRATEGY_2_NAME = "Gap Extension Reversal"

STRATEGY_1_RULES = (
    ("BUY", "Today's Open > PDH → completed 1m CLOSE below PDH → later completed 1m CLOSE back to/above Today's Open"),
    ("SELL", "Today's Open < PDL → completed 1m CLOSE above PDL → later completed 1m CLOSE back to/below Today's Open"),
    ("Market filter", "NIFTY 500 must meet the configured BUY/SELL threshold"),
    ("Entry", "Current market price after qualification, respecting the Open-side rule"),
    ("Stop loss", "BUY = PDH • SELL = PDL"),
    ("Target", "Minimum configured risk/reward; default 1.25R"),
)

STRATEGY_2_RULES = (
    ("SELL", "Today's Open > PDH → extension above Open → completed 1m CLOSE below Open"),
    ("BUY", "Today's Open < PDL → extension below Open → completed 1m CLOSE above Open"),
    ("Market filter", "NIFTY 500 is a soft protective filter; strong opposite movement blocks the setup"),
    ("Entry", "Current market price from a fresh completed 1m trigger"),
    ("Stop loss", "SELL = trigger-day high • BUY = trigger-day low"),
    ("Target", "PDH for SELL • PDL for BUY, subject to minimum 1.25R"),
)


def strategy_metadata(strategy: str) -> dict:
    key = str(strategy).upper().strip()
    if key in {"STRATEGY_1", "S1", "OPEN_RETURN"}:
        return {
            "strategy": "STRATEGY_1",
            "name": STRATEGY_1_NAME,
            "version": STRATEGY_VERSION,
            "rules": STRATEGY_1_RULES,
        }
    if key in {"STRATEGY_2", "S2", "GAP_EXTENSION_REVERSAL"}:
        return {
            "strategy": "STRATEGY_2",
            "name": STRATEGY_2_NAME,
            "version": STRATEGY_VERSION,
            "rules": STRATEGY_2_RULES,
        }
    raise ValueError(f"Unknown strategy: {strategy}")
