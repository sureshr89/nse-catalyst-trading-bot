"""Shared Dhan NIFTY 500 live-data bridge.

The bridge owns the live-universe collection contract so every consumer uses the
same fresh snapshot rules. A cycle starts from a fresh universe request and is
accepted only when at least 98% of the expected NIFTY 500 symbols are returned
and validated inside the configured collection window.
"""
from datetime import datetime
import math
import threading
import time
import pandas as pd
from config.settings import LIVE_COLLECTION_WINDOW_SECONDS, MIN_DATA_COVERAGE_COUNT
from market import dhan_data

MAX_INSTRUMENTS_PER_REQUEST = 1000
MIN_REQUEST_TIMEOUT_SECONDS = 0.25
COLLECTION_WINDOW_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
REQUIRED_COVERAGE = MIN_DATA_COVERAGE_COUNT

_CACHE_LOCK = threading.RLock()
_CACHE_ROWS = pd.DataFrame()
_CACHE_KEY = None
_CACHE_AT = 0.0


def _clean_mapping(mapping):
    if mapping is None or mapping.empty or not {"SecurityId", "Symbol"}.issubset(mapping.columns):
        return pd.DataFrame(columns=["SecurityId", "Symbol"])
    clean = mapping[["SecurityId", "Symbol"]].copy()
    clean["SecurityId"] = pd.to_numeric(clean["SecurityId"], errors="coerce")
    clean = clean.dropna(subset=["SecurityId"])
    clean["SecurityId"] = clean["SecurityId"].astype("int64").astype(str)
    clean["Symbol"] = clean["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
    clean = clean[(clean["SecurityId"] != "") & (clean["Symbol"] != "")]
    return clean.drop_duplicates("Symbol").reset_index(drop=True)


def _parse_rows(response, mapping):
    data = response.get("data", {}).get("NSE_EQ", {}) if isinstance(response, dict) else {}
    clean = _clean_mapping(mapping)
    if clean.empty or not isinstance(data, dict):
        return pd.DataFrame()
    by_id = dict(zip(clean["SecurityId"], clean["Symbol"]))
    now_text = datetime.now().isoformat(timespec="seconds")
    rows = []
    for sid, item in data.items():
        sid = str(sid)
        if sid not in by_id or not isinstance(item, dict):
            continue
        ohlc = item.get("ohlc") or {}
        try:
            ltp = float(item.get("last_price")); prev = float(ohlc.get("close"))
            op = float(ohlc.get("open")); high = float(ohlc.get("high")); low = float(ohlc.get("low"))
            volume = float(item.get("volume") or 0)
            net_raw = item.get("net_change")
            net = float(net_raw) if net_raw is not None else ltp - prev
        except (TypeError, ValueError, OverflowError):
            continue
        values = (ltp, prev, op, high, low, net, volume)
        if not all(math.isfinite(v) for v in values):
            continue
        if any(v <= 0 for v in (ltp, prev, op, high, low)) or volume < 0:
            continue
        if high < max(op, low, ltp) or low > min(op, high, ltp):
            continue
        rows.append({
            "Symbol": by_id[sid], "SecurityId": sid, "LTP": ltp,
            "TodayOpen": op, "TodayHigh": high, "TodayLow": low,
            "TodayClose": ltp, "PreviousClose": prev, "NetChange": net,
            "Volume": volume, "change_pct": (ltp - prev) / prev * 100.0,
            "UpdatedAt": now_text, "price_source": "DHAN_MARKETFEED_OHLC",
        })
    return pd.DataFrame(rows).drop_duplicates("Symbol").reset_index(drop=True) if rows else pd.DataFrame()


def _merge(existing, new_rows):
    if new_rows.empty:
        return existing.copy()
    if existing.empty:
        return new_rows.drop_duplicates("Symbol").reset_index(drop=True)
    return pd.concat([existing, new_rows], ignore_index=True).drop_duplicates("Symbol", keep="last").reset_index(drop=True)


def market_quote_partial(mapping):
    """Collect one fresh NIFTY 500 snapshot within the hard collection window.

    Missing symbols are retried inside the same cycle. Cached rows are never
    mixed into a new cycle because stale data must not satisfy the safety gate.
    """
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    clean = _clean_mapping(mapping)
    if clean.empty or len(clean) > MAX_INSTRUMENTS_PER_REQUEST or len(clean) < REQUIRED_COVERAGE:
        return pd.DataFrame()
    if not dhan_data.configured():
        return pd.DataFrame()

    expected = set(clean["SecurityId"].astype(str))
    fresh = pd.DataFrame()
    started = time.monotonic()
    attempts = 0

    while expected:
        elapsed = time.monotonic() - started
        remaining = COLLECTION_WINDOW_SECONDS - elapsed
        if remaining < MIN_REQUEST_TIMEOUT_SECONDS:
            break
        pending = clean[clean["SecurityId"].isin(expected)].copy()
        if pending.empty:
            break
        attempts += 1
        try:
            response = dhan_data._post(
                "/marketfeed/ohlc",
                {"NSE_EQ": pending["SecurityId"].tolist()},
                timeout=max(MIN_REQUEST_TIMEOUT_SECONDS, remaining),
            )
        except Exception:
            response = {}
        new_rows = _parse_rows(response, pending)
        if not new_rows.empty:
            fresh = _merge(fresh, new_rows)
            expected -= set(new_rows["SecurityId"].astype(str))
        elif remaining > 0.15:
            time.sleep(min(0.10, max(0.0, COLLECTION_WINDOW_SECONDS - (time.monotonic() - started))))
        if len(fresh) >= REQUIRED_COVERAGE or attempts >= 20:
            break

    elapsed = time.monotonic() - started
    coverage = len(fresh)
    if elapsed > COLLECTION_WINDOW_SECONDS or coverage < REQUIRED_COVERAGE:
        return pd.DataFrame()

    with _CACHE_LOCK:
        _CACHE_ROWS = fresh.copy()
        _CACHE_KEY = tuple(sorted(clean["SecurityId"].astype(str)))
        _CACHE_AT = time.monotonic()
    return fresh


def market_quote_partial_15s(mapping):
    return market_quote_partial(mapping)
