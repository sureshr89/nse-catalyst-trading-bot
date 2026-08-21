"""Isolated live NIFTY 500 Dhan diagnostic.
Uses Dhan LTP/OHLC endpoints directly so quote/depth failures cannot hide live prices.
No trading or journal writes.
"""
from __future__ import annotations
import os
from datetime import datetime
import pandas as pd
import requests

BASE_URL = "https://api.dhan.co/v2"

def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return str(value).strip()
    try:
        import streamlit as st
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""

def _configured() -> bool:
    return bool(_secret("DHAN_CLIENT_ID") and _secret("DHAN_ACCESS_TOKEN"))

def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": _secret("DHAN_ACCESS_TOKEN"),
        "client-id": _secret("DHAN_CLIENT_ID"),
    }

def _post(path: str, payload: dict):
    if not _configured():
        return {}, {"ok": False, "stage": "CONFIG", "message": "Dhan secrets missing", "http_status": None}
    try:
        response = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload, timeout=15)
        try:
            body = response.json()
        except Exception:
            body = {}
        if response.status_code != 200:
            message = body.get("errorMessage") or body.get("message") or response.text[:300]
            return body, {"ok": False, "stage": path, "message": str(message), "http_status": response.status_code}
        return body, {"ok": True, "stage": path, "message": "HTTP 200", "http_status": 200}
    except Exception as exc:
        return {}, {"ok": False, "stage": path, "message": f"{type(exc).__name__}: {exc}", "http_status": None}

def live_nifty500_ltp(mapping: pd.DataFrame) -> dict:
    if mapping is None or mapping.empty:
        return {"rows": pd.DataFrame(), "requested": 0, "returned": 0, "valid": 0, "status": {"ok": False, "stage": "MAPPING", "message": "Empty mapping"}}
    clean = mapping[["Symbol", "SecurityId"]].copy()
    clean["Symbol"] = clean["Symbol"].astype(str).str.upper().str.strip()
    clean["SecurityId"] = pd.to_numeric(clean["SecurityId"], errors="coerce")
    clean = clean.dropna(subset=["SecurityId"]).drop_duplicates("Symbol")
    ids = clean["SecurityId"].astype("int64").tolist()
    response, status = _post("/marketfeed/ltp", {"NSE_EQ": ids[:1000]})
    data = (response.get("data") or {}).get("NSE_EQ") if isinstance(response, dict) else None
    if not isinstance(data, dict):
        return {"rows": pd.DataFrame(), "requested": len(ids), "returned": 0, "valid": 0, "status": status, "raw_keys": list((response or {}).keys()) if isinstance(response, dict) else []}
    by_id = dict(zip(clean["SecurityId"].astype(str), clean["Symbol"]))
    rows = []
    for sid, item in data.items():
        if str(sid) not in by_id or not isinstance(item, dict):
            continue
        try:
            ltp = float(item.get("last_price"))
            if ltp <= 0:
                continue
            rows.append({"Symbol": by_id[str(sid)], "SecurityId": str(sid), "LTP": ltp, "UpdatedAt": datetime.now().isoformat(timespec="seconds"), "price_source": "DHAN_MARKETFEED_LTP"})
        except (TypeError, ValueError):
            continue
    return {"rows": pd.DataFrame(rows), "requested": len(ids), "returned": len(data), "valid": len(rows), "status": status, "raw_keys": list((response or {}).keys())}

def enrich_ohlc(mapping: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    if rows is None or rows.empty:
        return rows
    clean = mapping[["Symbol", "SecurityId"]].copy()
    clean["SecurityId"] = pd.to_numeric(clean["SecurityId"], errors="coerce")
    ids = clean.dropna(subset=["SecurityId"])["SecurityId"].astype("int64").tolist()
    response, _ = _post("/marketfeed/ohlc", {"NSE_EQ": ids[:1000]})
    data = (response.get("data") or {}).get("NSE_EQ") if isinstance(response, dict) else None
    if not isinstance(data, dict):
        return rows
    by_id = dict(zip(clean["SecurityId"].astype(str), clean["Symbol"]))
    extras = {}
    for sid, item in data.items():
        if str(sid) not in by_id or not isinstance(item, dict):
            continue
        o = item.get("ohlc") or {}
        try:
            extras[str(sid)] = {"TodayOpen": float(o.get("open") or 0), "TodayHigh": float(o.get("high") or 0), "TodayLow": float(o.get("low") or 0), "PreviousClose": float(o.get("close") or 0)}
        except (TypeError, ValueError):
            pass
    if not extras:
        return rows
    out = rows.copy()
    for col in ["TodayOpen", "TodayHigh", "TodayLow", "PreviousClose"]:
        out[col] = out["SecurityId"].map({sid: vals[col] for sid, vals in extras.items()})
    out["NetChange"] = out["LTP"] - out["PreviousClose"]
    out["change_pct"] = out["NetChange"] / out["PreviousClose"] * 100.0
    return out
