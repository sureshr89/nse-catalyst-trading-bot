"""Single integrated S1-S5 paper-trading engine entry point.

Also acts as the Streamlit entry point when Streamlit Cloud is configured
with the repository's default ``main.py`` file.
"""
from engine.master_engine import MasterEngine
from engine.dhan_patch import install as install_dhan_patch

# Use Dhan for the master NIFTY 500 / A-D / sector gates when configured.
# This remains paper-only and does not enable order placement.
install_dhan_patch(MasterEngine)

# Compatibility name used by the persistent worker.
TradingBot = MasterEngine

__all__ = ["TradingBot", "MasterEngine"]

# Streamlit Cloud can run the repository root main.py. Previously this file
# only defined the trading engine, so Streamlit rendered a completely blank
# page. Keep the worker import behaviour unchanged, but render the dashboard
# when this file is executed as the Streamlit script.
if __name__ == "__main__":
    from dashboard.single_master import *  # noqa: F401,F403
