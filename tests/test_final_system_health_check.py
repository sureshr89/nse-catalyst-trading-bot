"""Single smoke/integration check for the production data-to-paper pipeline."""
from pathlib import Path


def test_final_system_health_check():
    root = Path(__file__).resolve().parents[1]

    from engine.master_engine import MasterEngine
    from main import MasterEngine as DashboardMasterEngine
    from engine.cycle_runner import run_cycle
    from market import dhan_data
    from papertrade.paper_trade_engine import PaperTradeEngine
    from strategy import nifty500_price_action_strategies as strategies

    assert MasterEngine is not None
    assert PaperTradeEngine is not None
    assert callable(strategies.market_gate)
    assert callable(run_cycle)
    assert hasattr(DashboardMasterEngine, "run_cycle")

    # Approved market-data coverage gate: >=95% of NIFTY 500 = 475 symbols.
    assert strategies.market_gate("BUY", 0.1, 1.0, 1.1, 475, 8, 4)
    assert strategies.market_gate("SELL", -0.1, -1.0, 0.9, 475, 4, 8)
    assert not strategies.market_gate("BUY", 0.1, 1.0, 1.1, 474, 8, 4)

    # Dhan integration remains the production market-data source.
    assert hasattr(dhan_data, "configured")
    assert hasattr(dhan_data, "market_quote")
    assert hasattr(dhan_data, "map_nifty500")

    # Paper execution remains the only execution path exercised by this smoke test.
    assert hasattr(PaperTradeEngine, "open_trade")
    assert hasattr(PaperTradeEngine, "process_live_price")

    # Dashboard must exist and use the production engine entrypoint.
    dashboard = root / "dashboard" / "app.py"
    assert dashboard.exists()
    dashboard_source = dashboard.read_text(encoding="utf-8")
    assert "MasterEngine" in dashboard_source or "master_engine" in dashboard_source
