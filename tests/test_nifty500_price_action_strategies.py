"""Unit tests for the five NIFTY 500 OHLC/PDH/PDL strategy rules."""
from strategy.nifty500_price_action_strategies import market_gate,candle_gate,position_size,evaluate_s1,evaluate_s2,evaluate_s3,evaluate_s4,evaluate_s5

def test_market_gate_is_strict_at_plus_minus_quarter_percent():
    assert market_gate("BUY",0.26,1.01)
    assert market_gate("SELL",-0.26,0.99)
    assert not market_gate("BUY",0.25,1.5)
    assert not market_gate("SELL",-0.25,0.5)
    assert not market_gate("BUY",0.30,1.0)
    assert not market_gate("SELL",-0.30,1.0)

def test_previous_candle_direction():
    assert candle_gate("BUY",100,101)
    assert candle_gate("SELL",101,100)
    assert not candle_gate("BUY",101,100)
    assert not candle_gate("SELL",100,101)

def test_risk_band_accepts_only_valid_integer_quantity():
    assert position_size(100.0,99.0)==(1400,1.0,1400.0)
    assert position_size(100.0,0.0)==(14,100.0,1400.0)
    assert position_size(2000.0,400.0) is None

def test_s1_buy_and_sell():
    buy=evaluate_s1("ABC","BUY",110,100,90,98,115,110,True,False,0.26,1.2,100,101)
    sell=evaluate_s1("XYZ","SELL",90,100,95,85,102,90,False,True,-0.26,0.8,101,100)
    assert buy and buy.side=="BUY" and buy.stop_loss==98 and buy.previous_candle_color=="GREEN"
    assert sell and sell.side=="SELL" and sell.stop_loss==102 and sell.previous_candle_color=="RED"

def test_s2_buy_and_sell():
    buy=evaluate_s2("ABC","BUY",100,90,99,120,101,True,0.26,1.3,100,101)
    sell=evaluate_s2("XYZ","SELL",100,90,80,91,89,True,-0.26,0.7,101,100)
    assert buy and buy.stop_loss==99
    assert sell and sell.stop_loss==91

def test_s3_buy_and_sell():
    buy=evaluate_s3("ABC","BUY",110,120,100,98,115,110,True,False,0.26,1.2,100,101)
    sell=evaluate_s3("XYZ","SELL",90,100,80,85,102,90,False,True,-0.26,0.8,101,100)
    assert buy and buy.stop_loss==98
    assert sell and sell.stop_loss==102

def test_s4_buy_and_sell_use_previous_levels_only():
    buy=evaluate_s4("ABC","BUY",120,98,115,105,116,0.26,1.2,100,101)
    sell=evaluate_s4("XYZ","SELL",102,80,95,85,84,-0.26,0.8,101,100)
    assert buy and buy.stop_loss==105
    assert sell and sell.stop_loss==95

def test_s5_buy_and_sell():
    buy=evaluate_s5("ABC","BUY",100,90,101,0.26,1.2,100,101)
    sell=evaluate_s5("XYZ","SELL",100,90,89,-0.26,0.8,101,100)
    assert buy and buy.stop_loss==100
    assert sell and sell.stop_loss==90

def test_no_signal_when_market_or_candle_filter_fails():
    assert evaluate_s5("ABC","BUY",100,90,101,0.10,1.2,100,101) is None
    assert evaluate_s5("XYZ","SELL",100,90,89,-0.10,0.8,101,100) is None
    assert evaluate_s5("ABC","BUY",100,90,101,0.30,1.2,101,100) is None
    assert evaluate_s5("XYZ","SELL",100,90,89,-0.30,0.8,100,101) is None

def test_no_future_level_is_required_for_s4():
    assert evaluate_s4("ABC","BUY",120,98,115,105,115,0.26,1.2,100,101) is None
    assert evaluate_s4("XYZ","SELL",102,80,95,85,85,-0.26,0.8,101,100) is None
