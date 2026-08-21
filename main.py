"""Canonical NSE Catalyst production entrypoint.

The dashboard imports ``MasterEngine`` from this module.  The production
implementation itself lives in ``engine.master_engine`` so there is only one
runtime engine class and no duplicate engine state.
"""
from engine.master_engine import MasterEngine
from engine.cycle_runner import run_cycle as _run_cycle


def build_engine():
    """Create the canonical production engine used by the application."""
    return MasterEngine()


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine", "build_engine"]


if __name__ == "__main__":
    from dashboard.tabbed_app import render_dashboard
    render_dashboard()
