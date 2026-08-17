"""Immediate paper-entry market-price helper.

Uses the same bounded Yahoo request policy as PriceData and never retries a
failed request immediately, which helps avoid turning a temporary 429 into a
request storm.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from market.price_data import PriceData

INDIA_TZ=ZoneInfo("Asia/Kolkata")
_PRICE_DATA=PriceData()

def get_current_market_price(symbol, timeout=10):
    """Return the freshest available completed 1-minute market price."""
    try:
        candle=_PRICE_DATA.get_latest_available_1m(symbol)
        if not candle:return None
        stamp=pd.Timestamp(candle.get("Datetime")); stamp=stamp.tz_localize(INDIA_TZ) if stamp.tzinfo is None else stamp.tz_convert(INDIA_TZ)
        age=(datetime.now(INDIA_TZ)-stamp.to_pydatetime()).total_seconds()
        if age<0 or age>120:return None
        close=pd.to_numeric(pd.Series([candle.get("Close")]),errors="coerce").iloc[0]
        if pd.isna(close):return None
        return {"Close":float(close),"Datetime":stamp.to_pydatetime(),"price_source":"fresh_1m_market_price"}
    except Exception as error:
        print(f"Current market price failed for {symbol}: {type(error).__name__}: {error}"); return None
