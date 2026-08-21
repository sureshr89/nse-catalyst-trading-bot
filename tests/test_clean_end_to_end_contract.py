from config import settings
from strategy.nifty500_price_action_strategies import make_signal


def _market_buy():
    return dict(
        nifty500_change_pct=0.10,
        sector_alignment_pct=0.20,
        ad_ratio=1.20,
        ad_coverage=settings.MIN_DATA_COVERAGE_COUNT,
        positive_sectors=10,
        negative_sectors=5,
    )


def _market_sell():
    return dict(
        nifty500_change_pct=-0.10,
        sector_alignment_pct=-0.20,
        ad_ratio=0.80,
        ad_coverage=settings.MIN_DATA_COVERAGE_COUNT,
        positive_sectors=5,
        negative_sectors=10,
    )


def test_valid_buy_signal_reaches_trade_contract():
    signal = make_signal(
        "S1", "BUY", "ABC", 1000, 994,
        reason="clean S1 test",
        previous_candle_open=999,
        previous_candle_close=1000,
        **_market_buy(),
    )
    assert signal is not None
    assert signal.rr == settings.RISK_REWARD_RATIO
    assert settings.MIN_REQUIRED_RISK <= signal.actual_risk <= settings.MAX_RISK_PER_TRADE
    assert signal.target > signal.entry > signal.stop_loss
    assert signal.capital_used <= settings.ALLOCATED_CAPITAL_PER_TRADE


def test_valid_sell_signal_reaches_trade_contract():
    signal = make_signal(
        "S1", "SELL", "ABC", 1000, 1006,
        reason="clean S1 sell test",
        **_market_sell(),
    )
    assert signal is not None
    assert signal.target < signal.entry < signal.stop_loss
    assert settings.MIN_REQUIRED_RISK <= signal.actual_risk <= settings.MAX_RISK_PER_TRADE


def test_invalid_sell_market_alignment_is_rejected():
    signal = make_signal(
        "S1", "SELL", "ABC", 1000, 1006,
        reason="bad alignment",
        nifty500_change_pct=-0.10,
        sector_alignment_pct=0.20,
        ad_ratio=1.20,
        ad_coverage=settings.MIN_DATA_COVERAGE_COUNT,
        positive_sectors=10,
        negative_sectors=5,
    )
    assert signal is None


def test_coverage_boundary_is_strict():
    market = _market_buy()
    market["ad_coverage"] = settings.MIN_DATA_COVERAGE_COUNT - 1
    signal = make_signal(
        "S1", "BUY", "ABC", 1000, 994,
        reason="below coverage",
        **market,
    )
    assert signal is None


def test_position_sizing_rejects_risk_that_cannot_fit_maximum_band():
    signal = make_signal(
        "S1", "BUY", "ABC", 1000, 0.1,
        reason="risk too wide",
        **_market_buy(),
    )
    assert signal is None
