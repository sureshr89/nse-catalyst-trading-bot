"""Single integrated S1-S5 paper-trading engine entry point."""
from engine.master_engine import MasterEngine

# Compatibility name used by the persistent worker.
TradingBot = MasterEngine

__all__ = ["TradingBot", "MasterEngine"]
