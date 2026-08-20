from strategy.nifty500_price_action_strategies import make_signal

def test_valid_buy_signal_has_125r_and_bounded_risk():
    signal=make_signal('S1','BUY','ABC',100,98,1,1.0,1.5,500,'test',99,100,10,5)
    assert signal is not None
    assert signal.rr==1.25
    assert 1400 <= signal.actual_risk <= 1500
    assert signal.target > signal.entry > signal.stop_loss

def test_invalid_sell_market_alignment_is_rejected():
    signal=make_signal('S1','SELL','ABC',100,102,1,1.0,0.8,500,'test',101,100,5,10)
    assert signal is None
