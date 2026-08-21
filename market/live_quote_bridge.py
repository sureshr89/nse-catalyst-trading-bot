"""Shared Dhan NIFTY 500 live-data bridge.

One controlled collector builds one fresh NIFTY-500 market snapshot per cycle.
Dhan's market-feed API supports up to 1,000 instruments per request, so the
500-stock universe is fetched in one request per cycle.
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
CACHE_SECONDS = 0.0  # Every cycle must request fresh prices; never serve an old snapshot as fresh.
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
    """Return one fresh NIFTY-500 snapshot within the configured 15-second window.

    The caller treats the collection window as a hard safety deadline. This
    function never retries missing symbols and never uses a previous-cycle
    quote to increase fresh coverage. One request is used for the full 500
    universe, subject to Dhan's 1,000-instrument request limit.
    """
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    clean = _clean_mapping(mapping)
    if clean.empty or not dhan_data.configured() or len(clean) > MAX_INSTRUMENTS_PER_REQUEST:
        return pd.DataFrame()

    # No cache hit: every 15-second cycle must make a new market-feed request.
    started = time.monotonic()
    response = dhan_data._post(
        "/marketfeed/ohlc",
        {"NSE_EQ": clean["SecurityId"].tolist()},
        timeout=max(0.1, COLLECTION_WINDOW_SECONDS),
    )
    elapsed = time.monotonic() - started
    merged = _rows_from_response(response, clean)

    # A response arriving after the hard collection window is invalid even if
    # it contains 490+ rows. The next cycle must request all 500 again.
    if elapsed > COLLECTION_WINDOW_SECONDS:
        return pd.DataFrame()

    # Keep the last response only for diagnostics/backward compatibility; it is
    # never returned as a fresh snapshot on a later cycle.
    with _CACHE_LOCK:
        if not merged.empty:
            _CACHE_ROWS = merged.copy()
            _CACHE_KEY = tuple(sorted(clean["SecurityId"].tolist()))
            _CACHE_AT = time.monotonic()
    return merged


def market_quote_partial_15s(mapping):
    return market_quote_partial(mapping)
