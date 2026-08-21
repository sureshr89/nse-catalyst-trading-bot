"""Canonical NSE Catalyst production entrypoint.

The dashboard imports MasterEngine from this module. The production
implementation lives in engine.master_engine so there is one runtime engine.
"""
from engine.master_engine import MasterEngine
from engine.cycle_runner import run_cycle as _run_cycle

if not hasattr(MasterEngine, "run_cycle"):
    MasterEngine.run_cycle = _run_cycle


def build_engine():
    return MasterEngine()


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine", "build_engine"]


if __name__ == "__main__":
    from dashboard.single_master import render_dashboard
    render_dashboard()
