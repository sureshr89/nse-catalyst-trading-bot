"""NSE Catalyst root entrypoint for paper-trading engine and Streamlit dashboard."""
from engine.master_engine import MasterEngine
from engine.dhan_patch import install as install_dhan_patch
from engine.stability_patch import install as install_stability_patch, install_dhan_retry
from engine.live_data_alignment_patch import install as install_live_data_alignment_patch
from engine.execution_diagnostics_patch import install as install_execution_diagnostics_patch
from engine.trade_path_fix import install as install_trade_path_fix
from engine.diagnostic_consistency_patch import install as install_diagnostic_consistency_patch
from engine.authoritative_dhan_snapshot_patch import install as install_authoritative_dhan_snapshot_patch
from engine.strategy_diagnostics_patch import install as install_strategy_diagnostics_patch

install_dhan_retry()
install_dhan_patch(MasterEngine)
install_stability_patch(MasterEngine)
install_live_data_alignment_patch(MasterEngine)
install_trade_path_fix(MasterEngine)
install_diagnostic_consistency_patch(MasterEngine)
install_execution_diagnostics_patch(MasterEngine)
install_authoritative_dhan_snapshot_patch(MasterEngine)
install_strategy_diagnostics_patch(MasterEngine)
TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine"]

if __name__ == "__main__":
    from dashboard.single_master import render_dashboard
    from dashboard.test_tab import render_test_tab
    render_dashboard()
    render_test_tab()
