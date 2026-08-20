"""NSE Catalyst clean root entrypoint."""
from engine.master_engine import MasterEngine as _MasterEngine
from engine.cycle_runner import run_cycle


class MasterEngine(_MasterEngine):
    """Dashboard-facing engine with the canonical production cycle attached."""

    def run_cycle(self):
        return run_cycle(self)


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine"]

if __name__ == "__main__":
    from dashboard.tabbed_app import render_dashboard
    render_dashboard()
