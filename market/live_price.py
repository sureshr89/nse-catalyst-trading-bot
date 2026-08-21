"""Dhan-only live price adapter.

Provides the paper-trading SL/TP path without modifying PriceData at import time.
The canonical quote normalization and cache live in ``market.price_data``.
"""
from market.price_data import PriceData

_PRICE_DATA = PriceData()


def get_current_market_price(symbol, timeout=10):
    """Return the freshest valid Dhan LTP quote; no historical fallback."""
    return _PRICE_DATA.get_latest_live_price(symbol, max_age_seconds=0)


def get_latest_market_price(symbol, max_age_seconds=2):
    """Return a short-lived cached Dhan quote for paper monitoring."""
    return _PRICE_DATA.get_latest_live_price(symbol, max_age_seconds=max_age_seconds)
