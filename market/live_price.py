"""Dhan-only live market price adapter.

This module is read-only: it never places orders. Dhan is the sole live
market-data source so paper SL/TP monitoring cannot silently fall back to
stale Yahoo/Groww prices.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import pandas as pd
from market.price_data import PriceData
from market.dhan_data import configured as dhan_configured, map_nifty500, market_quote

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_PRICE_DATA = PriceData()
_DHAN_MAP = None
_DHAN_MAP_AT = 0.0


def _dhan_live(symbol):
    """Return a fresh Dhan OHLC/LTP quote, or None when unavailable."""
    global _DHAN_MAP, _DHAN_MAP_AT
    if not dhan_configured():
        return None

    clean = str(symbol).strip().upper().replace(".NS", "")
    if not clean:
        return None

    now = time.monotonic()
    if _DHAN_MAP is None or now - _DHAN_MAP_AT > 3600:
        try:
            _DHAN_MAP = map_nifty500([clean])
            _DHAN_MAP_AT = now
        except Exception as error:
            print(f"Dhan symbol mapping failed for {clean}: {type(error).__name__}: {error}")
            _DHAN_MAP = pd.DataFrame()
            _DHAN_MAP_AT = now

    if _DHAN_MAP is None or _DHAN_MAP.empty:
        return None

    try:
        quotes = market_quote(_DHAN_MAP, cache_seconds=5)
        if quotes.empty:
            return None
        row = quotes[quotes["Symbol"].astype(str).str.upper().eq(clean)]
        if row.empty:
            return None

        r = row.iloc[-1]
        value = float(r["LTP"])
        if value <= 0:
            return None

        return {
            "Close": value,
            "Datetime": datetime.now(INDIA_TZ),
            "Open": float(r["TodayOpen"]),
            "High": float(r["TodayHigh"]),
            "Low": float(r["TodayLow"]),
            "PreviousClose": float(r["PreviousClose"]),
            "price_source": "DHAN_OHLC",
        }
    except Exception as error:
        print(f"Dhan live price failed for {clean}: {type(error).__name__}: {error}")
        return None


def get_current_market_price(symbol, timeout=10):
    """Return the freshest Dhan LTP; never use a completed candle fallback."""
    return _dhan_live(symbol)


def _patched_get_latest_live_price(self, symbol, max_age_seconds=8):
    """Shared Dhan-only source for fast paper SL/TP monitoring."""
    return _dhan_live(symbol)


PriceData.get_latest_live_price = _patched_get_latest_live_price
