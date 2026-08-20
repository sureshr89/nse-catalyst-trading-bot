import inspect

from config import settings
from strategy.nifty500_price_action_strategies import STRATEGY_DEFINITIONS, evaluate


def test_strategy_contract_has_all_five_strategies():
    assert list(STRATEGY_DEFINITIONS) == ["S1", "S2", "S3", "S4", "S5"]
    for name in STRATEGY_DEFINITIONS:
        assert callable(evaluate)


def test_scan_interval_is_15_seconds():
    assert settings.SCAN_INTERVAL_SECONDS == 15


def test_market_observation_starts_at_0915():
    assert settings.MARKET_OPEN == "09:15"
    assert settings.OBSERVATION_START == "09:15"


def test_strategy_evaluator_signature_is_flexible():
    assert "strategy" in inspect.signature(evaluate).parameters
    assert any(p.kind == inspect.Parameter.VAR_KEYWORD for p in inspect.signature(evaluate).parameters.values())


def test_paper_only_safety():
    assert settings.PAPER_TRADING is True
    assert settings.LIVE_TRADING is False
