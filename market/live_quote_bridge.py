"""Partial Dhan quote bridge for live dashboard visibility.

Dashboard visibility is deliberately separate from the 475/500 trade gate.
Valid quotes returned by Dhan are retained individually even when coverage is
below 95%.  The bridge prefers the full quote endpoint and falls back to the
OHLC endpoint because the dashboard only requires LTP/OHLC/change data.
"""
from datetime import datetime
import math
import pandas as pd
from market import dhan_data


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
            net_raw = item.get("net_change")
            net = float(net_raw) if net_raw is not None else ltp - prev
            volume = float(item.get("volume") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(v) and v > 0 for v in (ltp, prev, op, hi, lo)):
            continue
        if hi < max(op, lo, ltp) or lo > min(op, hi, ltp):
            continue
        if not math.isfinite(net) or volume < 0:
            continue
        rows.append({
            "Symbol": by_id[sid], "SecurityId": sid, "LTP": ltp,
            "TodayOpen": op, "TodayHigh": hi, "TodayLow": lo,
            "TodayClose": ltp, "PreviousClose": prev, "NetChange": net,
            "Volume": volume, "change_pct": (ltp - prev) / prev * 100.0,
            "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
            "price_source": "DHAN_MARKETFEED_QUOTE",
        })
    return rows


def market_quote_partial(mapping):
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

    ids = clean["SecurityId"].tolist()

    # Full quote gives the richest data.  If that endpoint is unavailable or
    # returns no usable rows, OHLC is enough for the dashboard's stock values
    # and breadth calculations, so retry once with the simpler endpoint.
    response = dhan_data._marketfeed("NSE_EQ", ids, "/marketfeed/quote")
    rows = _rows_from_response(response, clean)

    if not rows:
        response = dhan_data._marketfeed("NSE_EQ", ids, "/marketfeed/ohlc")
        rows = _rows_from_response(response, clean)
        for row in rows:
            row["price_source"] = "DHAN_MARKETFEED_OHLC"

    return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
