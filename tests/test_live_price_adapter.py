"""Tests for the Dhan-only live price adapter."""
from datetime import datetime
from unittest.mock import patch

import pandas as pd

import market.live_price as live_price


def _quotes():
    return pd.DataFrame([{
        "Symbol": "RELIANCE",
        "LTP": 2500.0,
        "TodayOpen": 2490.0,
        "TodayHigh": 2510.0,
        "TodayLow": 2480.0,
        "PreviousClose": 2475.0,
    }])


def test_dhan_live_returns_ltp_and_source():
    with patch.object(live_price, "dhan_configured", return_value=True), \
         patch.object(live_price, "map_nifty500", return_value=pd.DataFrame([{"Symbol": "RELIANCE"}])), \
         patch.object(live_price, "market_quote", return_value=_quotes()):
        live_price._DHAN_MAP = None
        result = live_price.get_current_market_price("RELIANCE.NS")

    assert result["Close"] == 2500.0
    assert result["price_source"] == "DHAN_OHLC"
    assert isinstance(result["Datetime"], datetime)


def test_no_non_dhan_fallback_when_dhan_unavailable():
    with patch.object(live_price, "dhan_configured", return_value=False):
        result = live_price.get_current_market_price("RELIANCE")

    assert result is None


def test_price_data_patch_is_dhan_only():
    with patch.object(live_price, "_dhan_live", return_value=None) as dhan:
        result = live_price._PRICE_DATA.get_latest_live_price("RELIANCE")

    dhan.assert_called_once_with("RELIANCE")
    assert result is None
