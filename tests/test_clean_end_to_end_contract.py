from config import settings
from strategy.nifty500_price_action_strategies import make_signal


def test_valid_buy_signal_reaches_trade_contract():
    signal = make_signal('S1', 'BUY', 'ABC', 1000, 994, 0.10, 0.20, 1.20, settings.MIN_DATA_COVERAGE_COUNT, 'clean S1 test', 999, 1000, 10, 5)
    assert signal is not None
    assert signal.rr == 1.25
    assert 1400 <= signal.actual_risk <= 1500
    assert signal.target > signal.entry > signal.stop_loss
    assert signal.capital_used <= 250000


def test_invalid_sell_market_alignment_is_rejected():
    signal = make_signal('S1', 'SELL', 'ABC', 1000, 1006, -0.10, 0.20, 1.20, settings.MIN_DATA_COVERAGE_COUNT, 'bad alignment', 1001, 1000, 10, 5)
    assert signal is None
