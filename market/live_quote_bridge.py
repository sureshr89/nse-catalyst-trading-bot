"""Shared Dhan NIFTY 500 live-data bridge.

One controlled collector builds a single 15-second market snapshot. Quotes are
collected in small batches, merged by Symbol, and then reused by the engine,
dashboard, AD, sector calculations and S1-S5. The 98% rule is a trade-readiness
gate, not a reason to discard valid prices collected during the window.
"""
from datetime import datetime
import math
import threading
import time
import pandas as pd
from config.settings import LIVE_COLLECTION_WINDOW_SECONDS, MIN_DATA_COVERAGE_COUNT
from market import dhan_data

_CACHE_LOCK = threading.RLock()
_CACHE_ROWS = pd.DataFrame()
_CACHE_KEY = None
_CACHE_AT = 0.0
CACHE_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
COLLECTION_WINDOW_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
BATCH_SIZE = 100


def _rows_from_response(response, clean):
    data = (response.get("data", {}).get("NSE_EQ", {}) if isinstance(response, dict) else {})
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


def _merge(existing, incoming):
    if incoming is None or incoming.empty:
        return existing.copy() if existing is not None else pd.DataFrame()
    if existing is None or existing.empty:
        return incoming.copy().drop_duplicates("Symbol")
    combined = pd.concat([existing, incoming], ignore_index=True)
    # The latest valid observation wins for a symbol. This freezes the
    # collection window without losing earlier arrivals.
    combined = combined.drop_duplicates("Symbol", keep="last")
    return combined.reset_index(drop=True)


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
    """Return one shared 15-second merged NIFTY-500 snapshot.

    Dhan can return up to 1,000 instruments per request, but the collector uses
    100-instrument batches to make the collection incremental. Five batches can
    therefore arrive at different times and are merged into one snapshot.
    A second pass only retries still-missing batches if time remains. No 429
    retry burst is created and no partial quote is discarded merely because the
    final coverage is below 98%.
    """
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    clean = _clean_mapping(mapping)
    if clean.empty or not dhan_data.configured():
        return pd.DataFrame()
    key = tuple(sorted(clean["SecurityId"].tolist()))
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE_KEY == key and not _CACHE_ROWS.empty and now - _CACHE_AT < CACHE_SECONDS:
            return _CACHE_ROWS.copy()

    started = time.monotonic()
    merged = pd.DataFrame()
    batches = [clean.iloc[i:i + BATCH_SIZE].copy() for i in range(0, len(clean), BATCH_SIZE)]
    completed_batches = set()

    def collect_batch(batch_index, batch):
        nonlocal merged
        response = dhan_data._marketfeed("NSE_EQ", batch["SecurityId"].tolist(), "/marketfeed/ohlc")
        incoming = _rows_from_response(response, batch)
        if not incoming.empty:
            merged = _merge(merged, incoming)
        completed_batches.add(batch_index)

    # First pass: collect every batch once. The shared Dhan throttle enforces
    # the API request interval across the whole process.
    for idx, batch in enumerate(batches):
        if time.monotonic() - started >= COLLECTION_WINDOW_SECONDS:
            break
        collect_batch(idx, batch)

    # Second pass: only retry batches that produced no rows, and only while the
    # same 15-second collection window is still open.
    if len(merged) < min(MIN_DATA_COVERAGE_COUNT, len(clean)):
        missing = []
        merged_symbols = set(merged.get("Symbol", pd.Series(dtype=str)).astype(str).str.upper())
        for idx, batch in enumerate(batches):
            if time.monotonic() - started >= COLLECTION_WINDOW_SECONDS:
                break
            if not set(batch["Symbol"]).issubset(merged_symbols):
                missing.append((idx, batch))
        for idx, batch in missing:
            if time.monotonic() - started >= COLLECTION_WINDOW_SECONDS:
                break
            collect_batch(idx, batch)

    merged = merged.drop_duplicates("Symbol").reset_index(drop=True) if not merged.empty else pd.DataFrame()
    with _CACHE_LOCK:
        _CACHE_ROWS = merged.copy()
        _CACHE_KEY = key
        _CACHE_AT = time.monotonic()
    return merged


# Backward-compatible name for existing callers. It now uses the same merged
# 15-second snapshot and never performs a second independent 500-stock fetch.
def market_quote_partial_15s(mapping):
    return market_quote_partial(mapping)
