from papertrade.paper_trade_engine import PaperTradeEngine

def test_live_trading_is_disabled_by_contract():
    engine = PaperTradeEngine.__new__(PaperTradeEngine)
    engine.paper_trading = True
    engine.live_trading = True
    result = engine._validate_trade({"approved": True})
    assert result[0] is None
    assert "Live trading" in result[1]

def test_unapproved_trade_is_rejected():
    engine = PaperTradeEngine.__new__(PaperTradeEngine)
    engine.paper_trading = True
    engine.live_trading = False
    result = engine._validate_trade({"approved": False})
    assert result[0] is None
    assert "approved" in result[1]

def test_invalid_signal_is_rejected():
    engine = PaperTradeEngine.__new__(PaperTradeEngine)
    engine.paper_trading = True
    engine.live_trading = False
    result = engine._validate_trade({"approved": True, "symbol": "ABC", "signal": "HOLD"})
    assert result[0] is None
    assert "Invalid signal" in result[1]
