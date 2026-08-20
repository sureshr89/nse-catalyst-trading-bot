import pytest
from strategy.contracts import STRATEGY_VERSION, STRATEGY_RULES, strategy_metadata

def test_only_canonical_s1_to_s5_are_accepted():
    assert set(STRATEGY_RULES) == {"S1", "S2", "S3", "S4", "S5"}
    for key in STRATEGY_RULES:
        meta = strategy_metadata(key)
        assert meta["strategy"] == key
        assert meta["version"] == STRATEGY_VERSION

@pytest.mark.parametrize("legacy", ["OPEN_RETURN", "STRATEGY_1", "STRATEGY_2", "STRATEGY_3", "STRATEGY_4", "STRATEGY_5"])
def test_legacy_strategy_names_are_rejected(legacy):
    with pytest.raises(ValueError):
        strategy_metadata(legacy)

def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        strategy_metadata("S6")
