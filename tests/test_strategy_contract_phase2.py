from strategy.nifty500_price_action_strategies import market_gate, position_size

def test_market_gate_requires_full_nifty500_coverage():
    assert market_gate('BUY',1,0.5,1.2,499,10,5) is False
    assert market_gate('BUY',1,0.5,1.2,500,10,5) is True

def test_position_size_stays_inside_risk_and_capital_limits():
    result=position_size(1000,998.5)
    assert result is not None
    qty,rps,risk,capital=result
    assert 1400 <= risk <= 1500
    assert capital <= 250000
