"""Tests for the Dhan-only live price adapter."""
from datetime import datetime
from unittest.mock import patch

import market.live_price as live_price


def _result():
    return {
        "Symbol": "RELIANCE",
        "Close": 2500.0,
        "TodayOpen": 2490.0,
        "TodayHigh": 2510.0,
        "TodayLow": 2480.0,
        "PreviousClose": 2475.0,
        "price_source": "DHAN_MARKETFEED_QUOTE",
        "Datetime": datetime.now(),
    }


def test_dhan_live_returns_ltp_and_source():
    with patch.object(live_price._PRICE_DATA, "get_latest_live_price", return_value=_result()) as getter:
        result = live_price.get_current_market_price("RELIANCE.NS")
    getter.assert_called_once_with("RELIANCE.NS", max_age_seconds=0)
    assert result["Close"] == 2500.0
    assert result["price_source"] == "DHAN_MARKETFEED_QUOTE"
    assert isinstance(result["Datetime"], datetime)


def test_no_non_dhan_fallback_when_dhan_unavailable():
    with patch.object(live_price._PRICE_DATA, "get_latest_live_price", return_value=None) as getter:
        result = live_price.get_current_market_price("RELIANCE")
    getter.assert_called_once_with("RELIANCE", max_age_seconds=0)
    assert result is None


def test_price_data_is_the_only_live_price_boundary():
    with patch.object(live_price._PRICE_DATA, "get_latest_live_price", return_value=None) as getter:
        result = live_price.get_latest_market_price("RELIANCE", max_age_seconds=2)
    getter.assert_called_once_with("RELIANCE", max_age_seconds=2)
    assert result is None
