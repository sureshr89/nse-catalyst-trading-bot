"""Shared Dhan NIFTY 500 live-data bridge.

Build one fresh NIFTY-500 snapshot per 15-second collection cycle. The collector
uses the full 15 seconds as a hard deadline: if the first request returns only
part of the universe, subsequent requests fetch only the missing symbols while
time remains. A cycle is accepted only when fresh coverage reaches the
configured safety gate (>=490/500); otherwise the entire cycle is discarded.
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
CACHE_SECONDS = 0.0
COLLECTION_WINDOW_SECONDS = float(LIVE_COLLECTION_WINDOW_SECONDS)
MAX_INSTRUMENTS_PER_REQUEST = 1000
MIN_REQUEST_TIMEOUT_SECONDS = 0.25


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


def _merge_fresh_rows(existing, new_rows):
    if new_rows.empty:
        return existing.copy()
    if existing.empty:
        return new_rows.drop_duplicates("Symbol").reset_index(drop=True)
    merged = pd.concat([existing, new_rows], ignore_index=True)
    return merged.drop_duplicates("Symbol", keep="last").reset_index(drop=True)


def market_quote_partial(mapping):
    """Collect fresh NIFTY-500 quotes using the entire 15-second window.

    The first request asks for the complete universe. If Dhan returns only a
    partial response, the collector immediately retries *only the symbols that
    are still missing*. Each retry is bounded by the time remaining in the same
    15-second collection window; it never starts another 15-second timeout.

    Example: if 400/500 arrive after 10 seconds, the next request contains only
    the remaining 100 and has at most 5 seconds available. At the 15-second
    deadline, coverage is evaluated. If it is below the safety threshold, the
    cycle is invalid and the next outer cycle starts a completely fresh pull.
    """
    global _CACHE_ROWS, _CACHE_KEY, _CACHE_AT
    clean = _clean_mapping(mapping)
    if clean.empty or not dhan_data.configured() or len(clean) > MAX_INSTRUMENTS_PER_REQUEST:
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

        # Request only the symbols still missing. The first attempt is the full
        # 500; later attempts are targeted retries for the missing remainder.
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
            # A transient request failure should not poison already collected
            # fresh rows. Continue while the same 15-second deadline permits.
            continue

        new_rows = _rows_from_response(response, pending)
        if not new_rows.empty:
            fresh = _merge_fresh_rows(fresh, new_rows)
            received = set(new_rows["SecurityId"].astype(str))
            expected -= received
        else:
            # Avoid a tight retry loop when the API immediately returns an
            # empty/error response; consume a small amount of the remaining
            # window before trying again.
            time.sleep(min(0.10, max(0.0, COLLECTION_WINDOW_SECONDS - (time.monotonic() - started))))

        # A successful >=490 snapshot is sufficient; do not waste time making
        # extra requests for the final few symbols.
        if len(fresh) >= max(490, math.ceil(0.98 * len(clean))):
            break

        if attempts >= 20:
            break

    elapsed = time.monotonic() - started
    coverage = len(fresh)
    required = max(490, math.ceil(0.98 * len(clean)))

    # Hard deadline: data collected after 15 seconds is never accepted.
    # Hard safety gate: fewer than 490 fresh stocks invalidates this cycle.
    if elapsed > COLLECTION_WINDOW_SECONDS or coverage < required:
        return pd.DataFrame()

    with _CACHE_LOCK:
        _CACHE_ROWS = fresh.copy()
        _CACHE_KEY = tuple(sorted(clean["SecurityId"].tolist()))
        _CACHE_AT = time.monotonic()
    return fresh


def market_quote_partial_15s(mapping):
    return market_quote_partial(mapping)
