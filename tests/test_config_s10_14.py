from datetime import datetime
from config import settings, trading_limits, trading_rules


def test_single_s1_s5_market_contract():
    assert settings.STOCK_UNIVERSE == "NIFTY_500"
    assert settings.MAX_STOCKS == 500
    assert settings.PAPER_TRADING is True
    assert settings.LIVE_TRADING is False
    # 15s collection window + 10s decision window = 25s cycle.
    assert settings.COLLECTION_WINDOW_SECONDS == 15
    assert settings.DECISION_WINDOW_SECONDS == 10
    assert settings.SCAN_INTERVAL_SECONDS == 25


def test_trading_window_and_square_off():
    assert trading_rules.entry_allowed(datetime(2026, 8, 20, 9, 44)) is False
    assert trading_rules.entry_allowed(datetime(2026, 8, 20, 9, 45)) is True
    assert trading_rules.entry_allowed(datetime(2026, 8, 20, 14, 0)) is True
    assert trading_rules.entry_allowed(datetime(2026, 8, 20, 14, 1)) is False
    assert trading_rules.force_square_off(datetime(2026, 8, 20, 15, 0)) is True


def test_risk_limits_are_consistent():
    assert settings.ALLOCATED_CAPITAL_PER_TRADE == trading_limits.CAPITAL_PER_TRADE == trading_rules.CAPITAL_PER_STRATEGY
    assert settings.MIN_REQUIRED_RISK == trading_limits.MIN_TRADE_RISK == trading_rules.RISK_MIN
    assert settings.MAX_RISK_PER_TRADE == trading_limits.MAX_TRADE_RISK == trading_rules.RISK_MAX
    assert settings.RISK_REWARD_RATIO == trading_limits.TARGET_R_MULTIPLE == trading_rules.TARGET_RR
    assert settings.MAX_TRADES_PER_STRATEGY_PER_DAY == trading_limits.MAX_TRADES_PER_STRATEGY_PER_DAY == trading_rules.MAX_TRADES_PER_STRATEGY_DAY


def test_no_legacy_profit_target_is_active():
    assert settings.DAILY_PROFIT_TARGET is None
