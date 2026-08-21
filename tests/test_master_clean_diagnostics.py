from engine.master_engine import MasterEngine


def test_master_diagnostics_use_clean_dhan_s1_s5_contract():
    engine = MasterEngine.__new__(MasterEngine)
    diag = engine._blank_diag()
    assert diag["strategy"] == "S1-S5"
    assert diag["strategy_version"] == "clean-dhan-v3"
    assert diag["market_data_source"] == "DHAN_ONLY"
    assert diag["trade_path_status"] == "BLOCKED"
    assert diag["market_data_coverage"] == "0/500"
    assert diag["sector_mapping"] == "0/500"
    assert diag["ad_coverage"] == "0/500"
    assert set(diag["signals_by_strategy"]) == {"S1", "S2", "S3", "S4", "S5"}


def test_master_blocks_when_universe_is_not_exactly_500():
    engine = MasterEngine.__new__(MasterEngine)
    engine.references = __import__("pandas").DataFrame({"Symbol": ["ABC"]})
    engine.sector_map = __import__("pandas").DataFrame({"Symbol": ["ABC"]})
    engine.diagnostics = engine._blank_diag()
    engine.last_snapshot = {}
    engine._session_date = None
    engine._refresh_reference_data = lambda force=False: None
    snap = engine._market_snapshot()
    assert snap["verified"] is False
    assert snap["dhan_quotes"] == {}
