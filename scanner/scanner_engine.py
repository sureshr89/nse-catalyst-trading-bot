"""Compatibility scanner facade for the canonical S1-S5 paper-trading engine.

The scanner must not own a second copy of strategy logic.  Runtime signal
creation belongs to :class:`engine.master_engine.MasterEngine`, which applies
Dhan-only data, the NIFTY 500 market gate, S1-S5 rules, position sizing, and
paper-trading limits consistently.
"""
from __future__ import annotations

from typing import Any

from strategy.contracts import STRATEGY_VERSION


class ScannerEngine:
    """Thin compatibility wrapper around the canonical :class:`MasterEngine`.

    ``initial_side`` is retained for older callers but is deliberately derived
    from the current S1/S3/S5 open-vs-PDH/PDL semantics instead of importing a
    non-existent legacy strategy module.
    """

    def __init__(self):
        self.strategy_version = STRATEGY_VERSION
        self._master_engine = None

    @property
    def master_engine(self):
        """Lazily construct the canonical engine to avoid import-time side effects."""
        if self._master_engine is None:
            from engine.master_engine import MasterEngine

            self._master_engine = MasterEngine()
        return self._master_engine

    @staticmethod
    def initial_side(today_open: Any, pdh: Any, pdl: Any):
        """Return the deterministic opening side used by the open-based setups.

        Returns ``BUY`` when the open is above PDH, ``SELL`` when it is below
        PDL, ``None`` when the open is inside the PDH/PDL range, and ``None``
        for invalid/non-finite inputs.
        """
        try:
            opening = float(today_open)
            previous_high = float(pdh)
            previous_low = float(pdl)
        except (TypeError, ValueError):
            return None

        import math

        if not all(math.isfinite(value) for value in (opening, previous_high, previous_low)):
            return None
        if previous_low >= previous_high:
            return None
        if opening > previous_high:
            return "BUY"
        if opening < previous_low:
            return "SELL"
        return None

    def scan(self):
        """Run the canonical scanner through ``MasterEngine.scan()``."""
        return self.master_engine.scan()
