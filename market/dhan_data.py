"""DhanHQ market-data adapter used by the paper-trading scanner.

Credentials are read only from Streamlit Secrets or environment variables.
This module never submits orders. It provides instrument mapping, live OHLC/LTP
snapshots, and daily historical candles for PDH/PDL/PDC.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
import os
import threading
import time

import pandas as pd
import requests

BASE_URL = "https://api.dhan.co/v2"
MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
CACHE_DIR = Path("data")
MASTER_CACHE = CACHE_DIR / "dhan_scrip_master.csv"
IST = "Asia/Kolkata"

_LOCK = threading.RLock()
_QUOTE_CACHE: dict[str, dict] = {}
_QUOTE_CACHE_AT = 0.0
_REFERENCE_CACHE: dict[str, dict] = {}
_REFERENCE_CACHE_DATE = None


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return str(value).strip()
    try:
        import streamlit as st
        value = st.secrets.get(name, "")
        return str(value).strip()
    except Exception:
        return ""


def configured() -> bool:
    return bool(_secret("DHAN_CLIENT_ID") and _secret("DHAN_ACCESS_TOKEN"))


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": _secret("DHAN_ACCESS_TOKEN"),
        "client-id": _secret("DHAN_CLIENT_ID"),
    }


def _post(path: str, payload: dict, timeout: int = 15) -> dict:
    if not configured():
        return {}
    try:
        response = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload, timeout=timeout)
        if response.status_code != 200:
            print(f"Dhan {path} HTTP {response.status_code}: {response.text[:300]}")
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"Dhan {path} failed: {type(exc).__name__}: {exc}")
        return {}


def load_instrument_master(force: bool = False) -> pd.DataFrame:
    """Load Dhan's public instrument master."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if MASTER_CACHE.exists() and not force:
        try:
            frame = pd.read_csv(MASTER_CACHE, low_memory=False)
            if not frame.empty:
                return frame
        except Exception:
            pass
    try:
        response = requests.get(MASTER_URL, timeout=30)
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text), low_memory=False)
        frame.to_csv(MASTER_CACHE, index=False)
        return frame
    except Exception as exc:
        print(f"Dhan instrument master failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


def _col(frame: pd.DataFrame, names: tuple[str, ...]):
    lookup = {str(c).strip().upper(): c for c in frame.columns}
    for name in names:
        if name.upper() in lookup:
            return lookup[name.upper()]
    return None


def map_nifty500(symbols, force: bool = False) -> pd.DataFrame:
    """Map NIFTY 500 symbols to Dhan NSE_EQ security IDs."""
    wanted = {str(s).strip().upper().replace(".NS", "") for s in symbols if str(s).strip()}
    master = load_instrument_master(force=force)
    if master.empty or not wanted:
        return pd.DataFrame(columns=["Symbol", "SecurityId", "ExchangeSegment", "Instrument"])
    symbol_col = _col(master, ("SEM_TRADING_SYMBOL", "SYMBOL_NAME", "SM_SYMBOL_NAME", "DISPLAY_NAME"))
    security_col = _col(master, ("SEM_SECURITY_ID", "SECURITY_ID"))
    segment_col = _col(master, ("SEM_SEGMENT", "SEGMENT"))
    exchange_col = _col(master, ("SEM_EXM_EXCH_ID", "EXCH_ID"))
    instrument_col = _col(master, ("SEM_INSTRUMENT_NAME", "INSTRUMENT"))
    series_col = _col(master, ("SEM_SERIES", "SERIES"))
    if not symbol_col or not security_col:
        return pd.DataFrame(columns=["Symbol", "SecurityId", "ExchangeSegment", "Instrument"])
    frame = master.copy()
    frame["_symbol"] = frame[symbol_col].astype(str).str.strip().str.upper().str.replace(".NS", "", regex=False)
    if segment_col:
        frame = frame[frame[segment_col].astype(str).str.upper().eq("E")]
    if exchange_col:
        frame = frame[frame[exchange_col].astype(str).str.upper().eq("NSE")]
    if series_col:
        frame = frame[frame[series_col].astype(str).str.upper().isin({"EQ", "BE", "BZ", "SM", "ST", "SZ"})]
    frame = frame[frame["_symbol"].isin(wanted)].copy()
    frame["Symbol"] = frame["_symbol"]
    frame["SecurityId"] = frame[security_col].astype(str).str.strip()
    frame["ExchangeSegment"] = "NSE_EQ"
    frame["Instrument"] = frame[instrument_col].astype(str).str.upper() if instrument_col else "EQUITY"
    frame = frame[frame["SecurityId"].ne("") & frame["SecurityId"].ne("NAN")]
    return frame[["Symbol", "SecurityId", "ExchangeSegment", "Instrument"]].drop_duplicates("Symbol")


def _marketfeed(exchange_segment: str, security_ids: list[str], cache_seconds: int = 10) -> dict:
    if not configured() or not security_ids:
        return {}
    payload = {exchange_segment: [int(x) for x in security_ids[:1000]]}
    return _post("/marketfeed/ohlc", payload)


def market_quote(mapping: pd.DataFrame, cache_seconds: int = 10) -> pd.DataFrame:
    """Get LTP + today's OHLC + previous close for up to 1000 NSE equities."""
    global _QUOTE_CACHE, _QUOTE_CACHE_AT
    if mapping is None or mapping.empty or not configured():
        return pd.DataFrame()
    now = time.monotonic()
    with _LOCK:
        if _QUOTE_CACHE and now - _QUOTE_CACHE_AT <= cache_seconds:
            return pd.DataFrame(list(_QUOTE_CACHE.values()))
    ids = pd.to_numeric(mapping["SecurityId"], errors="coerce").dropna().astype(int).astype(str).tolist()
    response = _marketfeed("NSE_EQ", ids, cache_seconds)
    data = response.get("data", {}).get("NSE_EQ", {}) if response else {}
    rows = []
    by_id = dict(zip(mapping["SecurityId"].astype(str), mapping["Symbol"].astype(str)))
    for security_id, item in data.items():
        if not isinstance(item, dict):
            continue
        ohlc = item.get("ohlc") or {}
        try:
            rows.append({
                "Symbol": by_id.get(str(security_id), str(security_id)),
                "SecurityId": str(security_id),
                "LTP": float(item.get("last_price") or 0),
                "TodayOpen": float(ohlc.get("open") or 0),
                "TodayHigh": float(ohlc.get("high") or 0),
                "TodayLow": float(ohlc.get("low") or 0),
                "PreviousClose": float(ohlc.get("close") or 0),
                "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
            })
        except (TypeError, ValueError):
            continue
    result = pd.DataFrame(rows)
    if not result.empty:
        with _LOCK:
            _QUOTE_CACHE = {str(r["Symbol"]): r.to_dict() for _, r in result.iterrows()}
            _QUOTE_CACHE_AT = time.monotonic()
    return result


def index_quote(index_name: str = "NIFTY 500") -> dict | None:
    """Return a Dhan index LTP/OHLC snapshot for the named index."""
    master = load_instrument_master()
    if master.empty or not configured():
        return None
    name_col = _col(master, ("SEM_CUSTOM_SYMBOL", "SM_CUSTOM_SYMBOL", "DISPLAY_NAME", "SYMBOL_NAME"))
    security_col = _col(master, ("SEM_SECURITY_ID", "SECURITY_ID"))
    segment_col = _col(master, ("SEM_SEGMENT", "SEGMENT"))
    instrument_col = _col(master, ("SEM_INSTRUMENT_NAME", "INSTRUMENT"))
    if not name_col or not security_col:
        return None
    frame = master.copy()
    frame["_name"] = frame[name_col].astype(str).str.strip().str.upper()
    mask = frame["_name"].eq(index_name.upper())
    if not mask.any():
        mask = frame["_name"].str.contains(index_name.upper(), regex=False, na=False)
    if segment_col:
        mask &= frame[segment_col].astype(str).str.upper().eq("I")
    if instrument_col:
        mask &= frame[instrument_col].astype(str).str.upper().eq("INDEX")
    match = frame.loc[mask]
    if match.empty:
        return None
    security_id = str(match.iloc[0][security_col]).strip()
    response = _marketfeed("IDX_I", [security_id])
    item = (response.get("data", {}).get("IDX_I", {}) if response else {}).get(security_id)
    if not isinstance(item, dict):
        return None
    ohlc = item.get("ohlc") or {}
    try:
        return {"LTP": float(item.get("last_price") or 0), "Open": float(ohlc.get("open") or 0), "High": float(ohlc.get("high") or 0), "Low": float(ohlc.get("low") or 0), "PreviousClose": float(ohlc.get("close") or 0), "SecurityId": security_id}
    except (TypeError, ValueError):
        return None


def daily_history(security_id: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch daily OHLCV history for one NSE equity security."""
    response = _post("/charts/historical", {"securityId": str(security_id), "exchangeSegment": "NSE_EQ", "instrument": "EQUITY", "expiryCode": 0, "oi": False, "fromDate": from_date, "toDate": to_date}, timeout=20)
    if not response:
        return pd.DataFrame()
    try:
        frame = pd.DataFrame({"Open": response.get("open", []), "High": response.get("high", []), "Low": response.get("low", []), "Close": response.get("close", []), "Volume": response.get("volume", []), "Timestamp": response.get("timestamp", [])})
        if frame.empty:
            return frame
        frame["Datetime"] = pd.to_datetime(frame["Timestamp"], unit="s", utc=True).dt.tz_convert(IST)
        return frame.drop(columns=["Timestamp"]).sort_values("Datetime").reset_index(drop=True)
    except Exception as exc:
        print(f"Dhan daily history parse failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


def previous_day_references(mapping: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    """Build PDH/PDL/PDC once per trading day and cache it."""
    global _REFERENCE_CACHE, _REFERENCE_CACHE_DATE
    today = datetime.now().date()
    with _LOCK:
        if _REFERENCE_CACHE and _REFERENCE_CACHE_DATE == today and not force:
            return pd.DataFrame(list(_REFERENCE_CACHE.values()))
    if mapping is None or mapping.empty or not configured():
        return pd.DataFrame()
    rows = []
    from_date = (today - timedelta(days=10)).isoformat()
    to_date = (today + timedelta(days=1)).isoformat()
    for _, item in mapping.iterrows():
        history = daily_history(str(item["SecurityId"]), from_date, to_date)
        if history.empty:
            continue
        prior = history[history["Datetime"].dt.date < today]
        if prior.empty:
            continue
        row = prior.iloc[-1]
        rows.append({"Symbol": str(item["Symbol"]), "SecurityId": str(item["SecurityId"]), "PDH": float(row["High"]), "PDL": float(row["Low"]), "PreviousDayClose": float(row["Close"]), "PreviousDayOpen": float(row["Open"]), "PreviousDayVolume": float(row.get("Volume", 0) or 0)})
    result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
    with _LOCK:
        _REFERENCE_CACHE = {str(r["Symbol"]): r.to_dict() for _, r in result.iterrows()}
        _REFERENCE_CACHE_DATE = today
    return result
