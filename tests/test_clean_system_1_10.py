    source = (ROOT / "market" / "price_data.py").read_text(encoding="utf-8").lower()
    dhan = (ROOT / "market" / "dhan_data.py").read_text(encoding="utf-8").lower()
    assert "yfinance" not in source
    assert "yfinance" not in dhan
    assert "dhan" in source
    assert "dhan" in dhan


def test_05_strategy_rules_have_common_market_gate():
    from strategy.nifty500_price_action_strategies import market_gate
    # NIFTY 500 market-data coverage is a >=95% gate (475/500), not an exact 500 gate.
    assert market_gate("BUY", 0.1, 1.0, 1.1, 500, 8, 4)
    assert market_gate("SELL", -0.1, -1.0, 0.9, 500, 4, 8)
    assert market_gate("BUY", 0.1, 1.0, 1.1, 475, 8, 4)
    assert not market_gate("BUY", 0.1, 1.0, 1.1, 474, 8, 4)
    assert not market_gate("BUY", -0.1, 1.0, 1.1, 500, 8, 4)


def test_06_all_five_strategies_produce_correct_side_and_rr():
    from strategy.nifty500_price_action_strategies import evaluate_s1, evaluate_s2, evaluate_s3, evaluate_s4, evaluate_s5
    g = dict(nifty500_change_pct=0.2, sector_alignment_pct=1.0, ad_ratio=1.2, ad_coverage=500,
             positive_sectors=8, negative_sectors=4, previous_candle_open=100, previous_candle_close=101)
    assert evaluate_s1("T", "BUY", 110, 100, 90, 99, 115, 111, **g)
    assert evaluate_s2("T", "BUY", 100, 90, 99, 120, 101, True, **g)
    assert evaluate_s3("T", "BUY", 110, 120, 100, 98, 115, 111, **g)
    assert evaluate_s4("T", "BUY", 120, 98, 115, 105, 116, **g)
    assert evaluate_s5("T", "BUY", 100, 90, 101, **g)
    for fn, args in [