"""Live market price adapter.

Preferred source: Groww real-time LTP when GROWW_ACCESS_TOKEN is set.
Fallback: Yahoo/yfinance live 1-minute bar.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_PRICE_DATA = PriceData()
_ORIGINAL_LIVE = PriceData.get_latest_live_price
_GROWW = None


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
    try:
        exchange_symbol = f"NSE_{symbol}"
        response = client.get_ltp(segment=client.SEGMENT_CASH, exchange_trading_symbols=(exchange_symbol,))
        payload = response.get("payload", response) if isinstance(response, dict) else {}
        value = payload.get(exchange_symbol) if isinstance(payload, dict) else None
        if isinstance(value, dict):
            value = value.get("ltp") or value.get("last_price") or value.get("price")
        value = float(value)
        if value <= 0:
            return None
        now = datetime.now(INDIA_TZ)
        return {"Close": value, "Datetime": now, "Open": None, "High": None, "Low": None, "price_source": "GROWW_REALTIME_LTP"}
    except Exception:
        return None


def get_current_market_price(symbol, timeout=10):
    """Return the freshest live LTP; never require a completed candle."""
    live = _groww_live(symbol)
    if live is not None:
        return live
    try:
        latest = _ORIGINAL_LIVE(_PRICE_DATA, symbol, max_age_seconds=2)
        if latest is not None:
            latest["price_source"] = latest.get("price_source", "LIVE_1M_BAR")
            return latest
    except Exception as error:
        print(f"Current market price failed for {symbol}: {type(error).__name__}: {error}")
    return None


def _patched_get_latest_live_price(self, symbol, max_age_seconds=8):
    """Shared live source for the fast SL/TP position monitor."""
    live = _groww_live(symbol)
    if live is not None:
        return live
    return _ORIGINAL_LIVE(self, symbol, max_age_seconds=max_age_seconds)


# Scanner imports this module during application startup. Patch the shared
# PriceData class so position monitoring also uses the same live source.
PriceData.get_latest_live_price = _patched_get_latest_live_price
