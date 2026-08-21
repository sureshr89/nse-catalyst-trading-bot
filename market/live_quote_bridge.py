"""Shared Dhan NIFTY 500 live-data bridge.

One controlled collector builds one 15-second NIFTY-500 market snapshot.
Dhan's market-feed API supports up to 1,000 instruments per request, so the
500-stock universe is fetched in one request per cycle. The same snapshot is
reused by the engine, dashboard, AD, sectors and S1-S5.
"""
from datetime import datetime
import math
import threading
import time
import pandas as pd
from config.settings import LIVE_COLLECTION_WINDOW_SECONDS
from market import dhan_data

_CACHE_LOCK = threading.RLock()
_CACHE_ROWS = pd.DataFrame()
_CACHE_KEY = None
_CACHE_AT = 0.0
CACHE_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
COLLECTION_WINDOW_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
MAX_INSTRUMENTS_PER_REQUEST = 1000


def _rows_from_response(response, clean):
    data = response.get("data", {}).get("NSE_EQ", {}) if isinstance(response, dict) else {}
    by_id = dict(zip(clean["SecurityId"].astype(str), clean["Symbol"].astype(str).str.upper()))
    rows = []
    for sid, item in data.items():
        sid = str(sid)
        if sid not in by_id or not isinstance(item, dict):
            continue
        ohlc = item.get("ohlc") or {}
        try:
            ltp = float(item.get("last_price"))
            prev = float(ohlc.get("close"))
            op = float(ohlc.get("open"))
            hi = float(ohlc.get("high"))
            lo = float(ohlc.get("low"))
            volume = float(item.get("volume") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(v) and v > 0 for v in (ltp, prev, op, hi, lo)):
            continue
        if volume < 0 or hi < max(op, lo, ltp) or lo > min(op, hi, ltp):
            continue
        rows.append({
            "Symbol": by_id[sid], "SecurityId": sid, "LTP": ltp,
            "TodayOpen": op, "TodayHigh": hi, "TodayLow": lo,
            "TodayClose": ltp, "PreviousClose": prev, "NetChange": ltp - prev,
            "Volume": volume, "change_pct": (ltp - prev) / prev * 100.0,
            "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
            "price_source": "DHAN_MARKETFEED_OHLC",
        })
    return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()


def _clean_mapping(mapping):
    if mapping is None or mapping.empty or not {"SecurityId", "Symbol"}.issubset(mapping.columns):
        return pd.DataFrame()
    clean = mapping[["SecurityId", "Symbol"]].copy()
    clean["SecurityId"] = pd.to_numeric(clean["SecurityId"], errors="coerce")
    clean = clean.dropna(subset=["SecurityId"])
    clean["SecurityId"] = clean["SecurityId"].astype("int64").astype(str)
    clean["Symbol"] = clean["Symbol"].astype(str).str.upper().str.strip()
    return clean.drop_duplicates("Symbol").reset_index(drop=True)


def market_quote_partial(mapping):
    """Return one shared 15-second NIFTY-500 snapshot.

    The old implementation split 500 stocks into five 100-stock quote calls.
    Dhan documents up to 1,000 instruments per market-quote request, so those
    extra calls were unnecessary and could trigger 805/429 throttling. This
    implementation makes one bounded request for the full NIFTY 500 each cycle.
    """
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    clean = _clean_mapping(mapping)
    if clean.empty or not dhan_data.configured() or len(clean) > MAX_INSTRUMENTS_PER_REQUEST:
        return pd.DataFrame()
    key = tuple(sorted(clean["SecurityId"].tolist()))
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE_KEY == key and not _CACHE_ROWS.empty and now - _CACHE_AT < CACHE_SECONDS:
            return _CACHE_ROWS.copy()

    started = time.monotonic()
    response = dhan_data._marketfeed("NSE_EQ", clean["SecurityId"].tolist(), "/marketfeed/ohlc")
    merged = _rows_from_response(response, clean)
    elapsed = time.monotonic() - started

    with _CACHE_LOCK:
        if not merged.empty:
            _CACHE_ROWS = merged.copy()
            _CACHE_KEY = key
            _CACHE_AT = time.monotonic()
    return merged


# Backward-compatible name for existing callers.
def market_quote_partial_15s(mapping):
    return market_quote_partial(mapping)
