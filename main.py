"""Single integrated S1-S5 paper-trading engine entry point."""
from engine.master_engine import MasterEngine
from engine.dhan_patch import install as install_dhan_patch

# Use Dhan for the master NIFTY 500 / A-D / sector gates when configured.
# This remains paper-only and does not enable order placement.
install_dhan_patch(MasterEngine)

# Compatibility name used by the persistent worker.
TradingBot = MasterEngine

__all__ = ["TradingBot", "MasterEngine"]
