"""Canonical NSE Catalyst production entrypoint.

The dashboard imports ``MasterEngine`` from this module, so this file is kept
small and deliberately contains no duplicate market-data or strategy logic.
"""
from engine.master_engine import MasterEngine as _MasterEngine
from engine.cycle_runner import run_cycle as _run_cycle


class MasterEngine(_MasterEngine):
    """Dashboard-facing engine using the canonical production cycle."""

    def run_cycle(self):
        return _run_cycle(self)


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine", "build_engine"]


def build_engine():
    """Create the same engine instance used by the Streamlit application."""
    return MasterEngine()


if __name__ == "__main__":
    # Preserve the existing direct-entry dashboard behavior.
    from dashboard.tabbed_app import render_dashboard
    render_dashboard()
