"""Live market price adapter.

Preferred source: Groww real-time quote when GROWW_ACCESS_TOKEN is set.
Fallback: Yahoo/yfinance live 1-minute bar.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import time
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_PRICE_DATA = PriceData()
_ORIGINAL_LIVE = PriceData.get_latest_live_price
_GROWW = None
_GROWW_CACHE = {}
_GROWW_CACHE_AT = {}


def _groww_client():
    global _GROWW
    token = os.getenv("GROWW_ACCESS_TOKEN") or os.getenv("GROWW_API_TOKEN")
    if not token:
        return None
    if _GROWW is not None:
        return _GROWW
    try:
        from growwapi import GrowwAPI
        _GROWW = GrowwAPI(token)
        return _GROWW
    except Exception as error:
        print(f"Groww live-data adapter unavailable: {type(error).__name__}: {error}")
        return None


def _groww_live(symbol):
    client = _groww_client()
    if client is None:
        return None
    symbol = str(symbol).strip().upper().replace(".NS", "")
    if not symbol:
        return None
    now_mono = time.monotonic()
    cached = _GROWW_CACHE.get(symbol)
    if cached is not None and now_mono - _GROWW_CACHE_AT.get(symbol, 0.0) <= 1.0:
        return dict(cached)
    try:
        quote = client.get_quote(exchange=client.EXCHANGE_NSE, segment=client.SEGMENT_CASH, trading_symbol=symbol)
        payload = quote.get("payload", quote) if isinstance(quote, dict) else {}
        ltp = payload.get("last_price") or payload.get("price")
        ohlc = payload.get("ohlc") or {}
        if isinstance(ohlc, str):
            ohlc = {}
        value = float(ltp)
        if value <= 0:
            return None
        result = {
            "Close": value,
            "Datetime": datetime.now(INDIA_TZ),
            "Open": ohlc.get("open"),
            "High": ohlc.get("high"),
            "Low": ohlc.get("low"),
            "price_source": "GROWW_REALTIME_QUOTE",
        }
        _GROWW_CACHE[symbol] = dict(result)
        _GROWW_CACHE_AT[symbol] = time.monotonic()
        return result
    except Exception:
        return None


def _fallback_live(self, symbol, max_age_seconds=2):
    latest = _ORIGINAL_LIVE(self, symbol, max_age_seconds=max_age_seconds)
    if latest is None:
        return None
    latest = dict(latest)
    latest["Datetime"] = datetime.now(INDIA_TZ)
    latest["price_source"] = latest.get("price_source", "YAHOO_LIVE_1M_BAR")
    return latest


def get_current_market_price(symbol, timeout=10):
    """Return the freshest live LTP; never require a completed candle."""
    live = _groww_live(symbol)
    if live is not None:
        return live
    try:
        return _fallback_live(_PRICE_DATA, symbol, max_age_seconds=2)
    except Exception as error:
        print(f"Current market price failed for {symbol}: {type(error).__name__}: {error}")
    return None


def _patched_get_latest_live_price(self, symbol, max_age_seconds=8):
    """Shared live source for the fast SL/TP position monitor."""
    live = _groww_live(symbol)
    if live is not None:
        return live
    return _fallback_live(self, symbol, max_age_seconds=max_age_seconds)


PriceData.get_latest_live_price = _patched_get_latest_live_price
