"""Dhan-only live price adapter.

This module provides a single, fresh quote path for paper SL/TP monitoring.
It does not place orders and never falls back to historical candle closes.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from market.dhan_data import configured as dhan_configured, map_nifty500, market_quote
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_PRICE_DATA = PriceData()


def _dhan_live(symbol):
    clean = str(symbol).strip().upper().replace(".NS", "")
    if not clean or not dhan_configured():
        return None
    try:
        mapping = map_nifty500([clean])
    except Exception as error:
        print(f"Dhan symbol mapping failed for {clean}: {type(error).__name__}: {error}")
        return None
    if mapping is None or mapping.empty or len(mapping) != 1:
        return None
    try:
        quotes = market_quote(mapping, cache_seconds=2)
        if quotes is None or quotes.empty:
            return None
        row = quotes[quotes["Symbol"].astype(str).str.upper().eq(clean)]
        if row.empty:
            return None
        r = row.iloc[-1]
        values = {"Close": float(r["LTP"]), "Open": float(r["TodayOpen"]), "High": float(r["TodayHigh"]), "Low": float(r["TodayLow"]), "PreviousClose": float(r["PreviousClose"])}
        if any(pd.isna(v) or v <= 0 for v in values.values()):
            return None
        return {**values, "NetChange": float(r.get("NetChange", values["Close"] - values["PreviousClose"])), "Datetime": datetime.now(INDIA_TZ), "price_source": "DHAN_MARKETFEED_QUOTE"}
    except Exception as error:
        print(f"Dhan live price failed for {clean}: {type(error).__name__}: {error}")
        return None


def get_current_market_price(symbol, timeout=10):
    """Return the freshest valid Dhan LTP quote; no completed-candle fallback."""
    return _dhan_live(symbol)


def _patched_get_latest_live_price(self, symbol, max_age_seconds=8):
    """Use the canonical Dhan quote path for fast paper-trade monitoring."""
    return _dhan_live(symbol)


PriceData.get_latest_live_price = _patched_get_latest_live_price
