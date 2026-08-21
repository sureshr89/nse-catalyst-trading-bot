"""Canonical NSE Catalyst production entrypoint.

The dashboard imports the single MasterEngine from this module. Runtime cycle
orchestration is implemented directly by MasterEngine; this entrypoint does
not monkey-patch methods at import time.
"""
from engine.master_engine import MasterEngine


def build_engine():
    """Construct the canonical production engine."""
    return MasterEngine()


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine", "build_engine"]


if __name__ == "__main__":
    from dashboard.single_master import render_dashboard

    render_dashboard()
