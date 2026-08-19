"""Unit tests for the five NIFTY 500 OHLC/PDH/PDL strategy rules."""
from strategy.nifty500_price_action_strategies import (
    market_gate, position_size, evaluate_s1, evaluate_s2, evaluate_s3,
    evaluate_s4, evaluate_s5,
)


def test_market_gate_buy_and_sell_are_strict():
    assert market_gate("BUY", 0.01, 1.01)
    assert market_gate("SELL", -0.01, 0.99)
    assert not market_gate("BUY", 0.0, 1.5)
    assert not market_gate("BUY", 0.1, 1.0)
    assert not market_gate("SELL", 0.0, 0.5)
    assert not market_gate("SELL", -0.1, 1.0)


def test_risk_band_accepts_only_valid_integer_quantity():
    assert position_size(100.0, 99.0) == (1400, 1.0, 1400.0)
    assert position_size(100.0, 0.0) == (14, 100.0, 1400.0)
    # A ₹1,600 one-share risk cannot be reduced into the allowed band.
    assert position_size(2000.0, 400.0) is None


def test_s1_buy_and_sell():
    buy = evaluate_s1("ABC", "BUY", 110, 100, 90, 98, 115, 110, True, False, 0.5, 1.2)
    sell = evaluate_s1("XYZ", "SELL", 90, 100, 95, 85, 102, 90, False, True, -0.5, 0.8)
    assert buy and buy.side == "BUY" and buy.stop_loss == 98
    assert sell and sell.side == "SELL" and sell.stop_loss == 102


def test_s2_buy_and_sell():
    buy = evaluate_s2("ABC", "BUY", 100, 90, 99, 120, 101, True, 0.4, 1.3)
    sell = evaluate_s2("XYZ", "SELL", 100, 90, 80, 91, 89, True, -0.4, 0.7)
    assert buy and buy.stop_loss == 99
    assert sell and sell.stop_loss == 91


def test_s3_buy_and_sell():
    buy = evaluate_s3("ABC", "BUY", 110, 120, 100, 98, 115, 110, True, False, 0.4, 1.2)
    sell = evaluate_s3("XYZ", "SELL", 90, 100, 80, 85, 102, 90, False, True, -0.4, 0.8)
    assert buy and buy.stop_loss == 98
    assert sell and sell.stop_loss == 102


def test_s4_buy_and_sell_use_previous_levels_only():
    buy = evaluate_s4("ABC", "BUY", 120, 98, 115, 105, 116, 0.3, 1.2)
    sell = evaluate_s4("XYZ", "SELL", 102, 80, 95, 85, 84, -0.3, 0.8)
    assert buy and buy.stop_loss == 105
    assert sell and sell.stop_loss == 95


def test_s5_buy_and_sell():
    buy = evaluate_s5("ABC", "BUY", 100, 90, 101, 0.3, 1.2)
    sell = evaluate_s5("XYZ", "SELL", 100, 90, 89, -0.3, 0.8)
    assert buy and buy.stop_loss == 100
    assert sell and sell.stop_loss == 90


def test_no_signal_when_market_filter_fails():
    assert evaluate_s5("ABC", "BUY", 100, 90, 101, -0.1, 1.2) is None
    assert evaluate_s5("XYZ", "SELL", 100, 90, 89, 0.1, 0.8) is None


def test_no_future_level_is_required_for_s4():
    # Current price has not broken the previously formed high/low yet.
    assert evaluate_s4("ABC", "BUY", 120, 98, 115, 105, 115, 0.3, 1.2) is None
    assert evaluate_s4("XYZ", "SELL", 102, 80, 95, 85, 85, -0.3, 0.8) is None
