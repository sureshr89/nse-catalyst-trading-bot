"""NSE Catalyst root entrypoint for paper-trading engine and Streamlit dashboard."""
from engine.master_engine import MasterEngine
from engine.dhan_patch import install as install_dhan_patch

install_dhan_patch(MasterEngine)
TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine"]

if __name__ == "__main__":
    from dashboard.single_master import render_dashboard
    render_dashboard()
