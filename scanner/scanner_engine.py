"""Compatibility scanner facade backed by the unified MasterEngine/strategy contract."""
from __future__ import annotations

from strategy.open_reversal_engine import OpenReversalEngine
from strategy.contracts import STRATEGY_VERSION


class ScannerEngine:
    """Thin compatibility wrapper; runtime signal generation stays in the unified engine."""

    def __init__(self):
        self.strategy = OpenReversalEngine()
        self.strategy_version = STRATEGY_VERSION

    def initial_side(self, today_open, pdh, pdl):
        return self.strategy.initial_side(today_open, pdh, pdl)

    def scan(self):
        from engine.master_engine import MasterEngine
        return MasterEngine().scan()
