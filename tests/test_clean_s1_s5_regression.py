from config import settings
from strategy.contracts import STRATEGY_RULES
from strategy.nifty500_price_action_strategies import STRATEGY_DEFINITIONS

def test_clean_s1_s5_regression_contract():
    expected = {"S1", "S2", "S3", "S4", "S5"}
    assert set(STRATEGY_RULES) == expected
    assert set(STRATEGY_DEFINITIONS) == expected
    assert settings.STOCK_UNIVERSE == "NIFTY_500"
    assert settings.MAX_STOCKS == 500
    assert settings.PAPER_TRADING is True
    assert settings.LIVE_TRADING is False
    assert settings.MAX_TRADES_PER_STRATEGY_PER_DAY == 1
    assert settings.MAX_RISK_PER_TRADE == 1500
    assert settings.MIN_REQUIRED_RISK == 1400
    assert settings.MIN_RR_RATIO == 1.25
    assert settings.SQUARE_OFF_TIME == "15:00"
