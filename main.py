"""NSE Catalyst clean root entrypoint."""
from engine.master_engine import MasterEngine

TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine"]

if __name__ == "__main__":
    from dashboard.tabbed_app import render_dashboard
    render_dashboard()
