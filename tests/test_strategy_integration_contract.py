from strategy.contracts import STRATEGY_VERSION,strategy_metadata
from strategy.nifty500_price_action_strategies import STRATEGY_DEFINITIONS,evaluate_s1,evaluate_s2,evaluate_s3,evaluate_s4,evaluate_s5

def test_contract_contains_exactly_five_active_strategies():
    assert set(STRATEGY_DEFINITIONS)=={"S1","S2","S3","S4","S5"}
    assert {strategy_metadata(s)["strategy"] for s in STRATEGY_DEFINITIONS}==set(STRATEGY_DEFINITIONS)

def test_contract_version_is_clean_dhan_version():
    assert STRATEGY_VERSION.startswith("2026.08.20.clean-dhan")

def test_contract_has_no_legacy_strategy_alias_as_active_engine():
    assert strategy_metadata("STRATEGY_1")["strategy"]=="S1"
    assert strategy_metadata("STRATEGY_2")["strategy"]=="S2"

def test_s1_contract_requires_live_reclaim():
    kwargs={"nifty500_change_pct":1,"sector_alignment_pct":1,"ad_ratio":2,"ad_coverage":500,"positive_sectors":10,"negative_sectors":5,"previous_candle_open":100,"previous_candle_close":101}
    assert evaluate_s1("T","BUY",110,100,90,99,115,111,**kwargs) is not None
    assert evaluate_s1("T","BUY",110,100,90,99,115,109,**kwargs) is None
