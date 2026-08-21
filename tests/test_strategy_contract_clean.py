from strategy.contracts import STRATEGY_VERSION, STRATEGY_RULES, strategy_metadata
from strategy.nifty500_price_action_strategies import market_gate, position_size


def test_clean_contract_defines_exactly_s1_to_s5():
    assert set(STRATEGY_RULES) == {'S1','S2','S3','S4','S5'}
    assert STRATEGY_VERSION.startswith('2026.08.21.clean-dhan-')
    for key in STRATEGY_RULES:
        assert strategy_metadata(key)['strategy'] == key


def test_market_gate_requires_at_least_98_percent_coverage_and_directional_breadth():
    assert market_gate('BUY', 0.1, 0.2, 1.2, 500, 10, 5)
    assert market_gate('SELL', -0.1, -0.2, 0.8, 500, 5, 10)
    assert market_gate('BUY', 0.1, 0.2, 1.2, 490, 10, 5)
    assert market_gate('SELL', -0.1, -0.2, 0.8, 490, 5, 10)
    assert not market_gate('BUY', 0.1, 0.2, 1.2, 489, 10, 5)
    assert not market_gate('SELL', -0.1, -0.2, 0.8, 489, 5, 10)
    assert not market_gate('SELL', -0.1, -0.2, 0.8, 500, 10, 5)


def test_position_size_respects_capital_and_risk_band():
    result = position_size(1000, 994)
    assert result is not None
    qty, risk_per_share, risk, capital = result
    assert 1400 <= risk <= 1500
    assert capital <= 250000
    assert qty > 0 and risk_per_share == 6
