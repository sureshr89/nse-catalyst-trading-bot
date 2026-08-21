"""Unit tests for the clean S1-S5 NIFTY 500 strategy contract."""
from strategy.nifty500_price_action_strategies import market_gate,position_size,evaluate_s1,evaluate_s2,evaluate_s3,evaluate_s4,evaluate_s5
G_BUY={"nifty500_change_pct":0.10,"sector_alignment_pct":1.0,"ad_ratio":1.2,"ad_coverage":500,"positive_sectors":10,"negative_sectors":5,"previous_candle_open":100,"previous_candle_close":101}
G_SELL={"nifty500_change_pct":-0.10,"sector_alignment_pct":-1.0,"ad_ratio":0.8,"ad_coverage":500,"positive_sectors":5,"negative_sectors":10,"previous_candle_open":101,"previous_candle_close":100}

def test_market_gate_requires_verified_breadth_and_sector_count():
    assert market_gate("BUY",0.01,1,1.01,500,10,5);assert market_gate("SELL",-0.01,-1,0.99,500,5,10)
    assert market_gate("BUY",0.01,1,1.01,475,10,5);assert market_gate("SELL",-0.01,-1,0.99,475,5,10)
    assert not market_gate("BUY",0.01,1,1.01,474,10,5);assert not market_gate("BUY",0,1,1.2,500,10,5);assert not market_gate("BUY",0.1,1,1.2,500,5,10)

def test_risk_band_and_capital():
    assert position_size(100.0,99.0)==(1400,1.0,1400.0,140000.0);assert position_size(2000.0,400.0) is None;assert position_size(100.0,0.0) is None

def test_s1_requires_live_open_reclaim():
    buy=evaluate_s1("ABC","BUY",110,100,90,98,115,111,**G_BUY);assert buy and buy.stop_loss==100
    assert evaluate_s1("ABC","BUY",110,100,90,98,110,110,**G_BUY) is None
    sell=evaluate_s1("XYZ","SELL",90,100,95,85,102,89,**G_SELL);assert sell and sell.stop_loss==95
    assert evaluate_s1("XYZ","SELL",90,100,95,85,102,90,**G_SELL) is None

def test_s2_buy_and_sell():
    buy=evaluate_s2("ABC","BUY",100,90,99,120,101,True,**G_BUY);sell=evaluate_s2("XYZ","SELL",100,90,80,91,89,True,**G_SELL)
    assert buy and buy.stop_loss==99;assert sell and sell.stop_loss==91

def test_s3_buy_and_sell():
    buy=evaluate_s3("ABC","BUY",110,120,100,98,115,111,**G_BUY);sell=evaluate_s3("XYZ","SELL",90,100,80,85,102,89,**G_SELL)
    assert buy and buy.stop_loss==98;assert sell and sell.stop_loss==102

def test_s4_buy_and_sell():
    buy=evaluate_s4("ABC","BUY",120,98,115,105,116,**G_BUY);sell=evaluate_s4("XYZ","SELL",102,80,95,85,84,**G_SELL)
    assert buy and buy.stop_loss==105;assert sell and sell.stop_loss==95

def test_s5_buy_and_sell():
    buy=evaluate_s5("ABC","BUY",100,90,101,**G_BUY);sell=evaluate_s5("XYZ","SELL",100,90,89,**G_SELL)
    assert buy and buy.stop_loss==100;assert sell and sell.stop_loss==90

def test_invalid_breadth_blocks_signals():
    bad=dict(G_BUY);bad["ad_coverage"]=474;assert evaluate_s5("ABC","BUY",100,90,101,**bad) is None

def test_s4_does_not_use_future_current_extreme():
    assert evaluate_s4("ABC","BUY",120,98,115,105,115,**G_BUY) is None;assert evaluate_s4("XYZ","SELL",102,80,95,85,85,**G_SELL) is None
