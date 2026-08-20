from strategy.nifty500_price_action_strategies import position_size, RR, MIN_RISK, MAX_RISK, CAPITAL_PER_TRADE

def test_position_size_stays_inside_risk_and_capital_bounds():
    result = position_size(100.0, 95.0)
    assert result is not None
    qty, risk_per_share, risk, capital = result
    assert qty > 0
    assert MIN_RISK <= risk <= MAX_RISK
    assert capital <= CAPITAL_PER_TRADE
    assert risk == round(qty * risk_per_share, 2)

def test_position_size_rejects_impossible_risk_band():
    assert position_size(100.0, 99.99) is None
    assert position_size(100.0, 1.0) is None

def test_target_ratio_is_1_25r():
    assert RR == 1.25
