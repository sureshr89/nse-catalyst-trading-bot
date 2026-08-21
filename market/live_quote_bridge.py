"""Shared Dhan NIFTY 500 live-data bridge.

One shared OHLC snapshot is used by the trading engine and dashboard.  This
prevents the Streamlit fragments from independently hitting Dhan's 1-request-
per-second Quote API and triggering error 805.
"""
from datetime import datetime
import math
import threading
import time
import pandas as pd
from market import dhan_data

_CACHE_LOCK = threading.RLock()
_CACHE_ROWS = pd.DataFrame()
_CACHE_KEY = None
_CACHE_AT = 0.0
# The app has multiple 15-second Streamlit fragments. Keep one snapshot long
# enough for all fragments in the same cycle to reuse it.
CACHE_SECONDS = 20.0


def _rows_from_response(response, clean):
    data = (response.get("data", {}).get("NSE_EQ", {}) if isinstance(response, dict) else {})
    by_id = dict(zip(clean["SecurityId"], clean["Symbol"]))
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
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(v) and v > 0 for v in (ltp, prev, op, hi, lo)):
            continue
        if hi < max(op, lo, ltp) or lo > min(op, hi, ltp):
            continue
        net = ltp - prev
        rows.append({
            "Symbol": by_id[sid], "SecurityId": sid, "LTP": ltp,
            "TodayOpen": op, "TodayHigh": hi, "TodayLow": lo,
            "TodayClose": ltp, "PreviousClose": prev, "NetChange": net,
            "Volume": float(item.get("volume") or 0),
            "change_pct": (ltp - prev) / prev * 100.0,
            "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
            "price_source": "DHAN_MARKETFEED_OHLC",
        })
    return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()


def market_quote_partial(mapping):
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    if mapping is None or mapping.empty or not dhan_data.configured():
        return pd.DataFrame()
    if not {"SecurityId", "Symbol"}.issubset(mapping.columns):
        return pd.DataFrame()

    clean = mapping[["SecurityId", "Symbol"]].copy()
    clean["SecurityId"] = pd.to_numeric(clean["SecurityId"], errors="coerce")
    clean = clean.dropna(subset=["SecurityId"])
    clean["SecurityId"] = clean["SecurityId"].astype("int64").astype(str)
    clean["Symbol"] = clean["Symbol"].astype(str).str.upper().str.strip()
    clean = clean.drop_duplicates("Symbol")
    if clean.empty:
        return pd.DataFrame()

    key = tuple(sorted(clean["SecurityId"].tolist()))
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE_KEY == key and not _CACHE_ROWS.empty and now - _CACHE_AT < CACHE_SECONDS:
            return _CACHE_ROWS.copy()
        response = dhan_data._marketfeed("NSE_EQ", clean["SecurityId"].tolist(), "/marketfeed/ohlc")
        rows = _rows_from_response(response, clean)
        if not rows.empty:
            _CACHE_ROWS = rows.copy()
            _CACHE_KEY = key
            _CACHE_AT = time.monotonic()
        return rows
