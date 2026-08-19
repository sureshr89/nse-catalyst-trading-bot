"""DhanHQ market-data adapter with explicit API diagnostics."""
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
_QUOTE_CACHE = {}
_QUOTE_CACHE_AT = 0.0
_LAST_DHAN_STATUS = {"ok": False, "stage": "NOT_TESTED", "http_status": None, "error_code": None, "message": "Not tested", "received": 0, "requested": 0, "updated_at": None}


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return str(value).strip()
    try:
        import streamlit as st
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def configured() -> bool:
    return bool(_secret("DHAN_CLIENT_ID") and _secret("DHAN_ACCESS_TOKEN"))


def dhan_status() -> dict:
    return dict(_LAST_DHAN_STATUS)


def _set_status(**kwargs):
    global _LAST_DHAN_STATUS
    _LAST_DHAN_STATUS = {**_LAST_DHAN_STATUS, **kwargs, "updated_at": datetime.now().isoformat(timespec="seconds")}


def _headers():
    return {"Accept": "application/json", "Content-Type": "application/json", "access-token": _secret("DHAN_ACCESS_TOKEN"), "client-id": _secret("DHAN_CLIENT_ID")}


def _post(path: str, payload: dict, timeout: int = 15) -> dict:
    if not configured():
        _set_status(ok=False, stage="CONFIG", message="DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN missing")
        return {}
    try:
        response = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload, timeout=timeout)
        try: body = response.json()
        except Exception: body = {}
        if response.status_code != 200:
            code = body.get("errorCode") or body.get("error_code") or body.get("code") if isinstance(body, dict) else None
            msg = body.get("errorMessage") or body.get("error_message") or body.get("message") if isinstance(body, dict) else response.text[:300]
            _set_status(ok=False, stage=path, http_status=response.status_code, error_code=code, message=str(msg), requested=sum(len(v) for v in payload.values() if isinstance(v, list)))
            return {}
        _set_status(ok=True, stage=path, http_status=200, error_code=None, message="Dhan API response received")
        return body if isinstance(body, dict) else {}
    except Exception as exc:
        _set_status(ok=False, stage=path, message=f"{type(exc).__name__}: {exc}")
        return {}


def load_instrument_master(force=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if MASTER_CACHE.exists() and not force:
        try:
            x = pd.read_csv(MASTER_CACHE, low_memory=False)
            if not x.empty: return x
        except Exception: pass
    try:
        r = requests.get(MASTER_URL, timeout=30); r.raise_for_status()
        x = pd.read_csv(StringIO(r.text), low_memory=False); x.to_csv(MASTER_CACHE, index=False); return x
    except Exception as exc:
        _set_status(ok=False, stage="INSTRUMENT_MASTER", message=f"{type(exc).__name__}: {exc}"); return pd.DataFrame()


def _col(frame, names):
    lookup = {str(c).strip().upper(): c for c in frame.columns}
    return next((lookup[n.upper()] for n in names if n.upper() in lookup), None)


def map_nifty500(symbols, force=False):
    wanted = {str(s).strip().upper().replace(".NS", "") for s in symbols if str(s).strip()}
    m = load_instrument_master(force)
    if m.empty or not wanted: return pd.DataFrame(columns=["Symbol","SecurityId","ExchangeSegment","Instrument"])
    sc=_col(m,("SEM_TRADING_SYMBOL","SYMBOL_NAME","SM_SYMBOL_NAME","DISPLAY_NAME")); ic=_col(m,("SEM_SECURITY_ID","SECURITY_ID")); seg=_col(m,("SEM_SEGMENT","SEGMENT")); ex=_col(m,("SEM_EXM_EXCH_ID","EXCH_ID")); ins=_col(m,("SEM_INSTRUMENT_NAME","INSTRUMENT")); ser=_col(m,("SEM_SERIES","SERIES"))
    if not sc or not ic: return pd.DataFrame(columns=["Symbol","SecurityId","ExchangeSegment","Instrument"])
    x=m.copy(); x["_symbol"]=x[sc].astype(str).str.strip().str.upper().str.replace(".NS","",regex=False)
    if seg: x=x[x[seg].astype(str).str.upper().eq("E")]
    if ex: x=x[x[ex].astype(str).str.upper().eq("NSE")]
    if ser: x=x[x[ser].astype(str).str.upper().isin({"EQ","BE","BZ","SM","ST","SZ"})]
    x=x[x["_symbol"].isin(wanted)].copy(); x["Symbol"]=x["_symbol"]; x["SecurityId"]=x[ic].astype(str).str.strip(); x["ExchangeSegment"]="NSE_EQ"; x["Instrument"]=x[ins].astype(str).str.upper() if ins else "EQUITY"
    return x[x["SecurityId"].ne("") & x["SecurityId"].ne("NAN")][["Symbol","SecurityId","ExchangeSegment","Instrument"]].drop_duplicates("Symbol")


def _marketfeed(exchange_segment, security_ids, endpoint="/marketfeed/quote"):
    ids=[int(x) for x in security_ids[:1000]]
    _set_status(stage=endpoint, requested=len(ids), received=0)
    return _post(endpoint,{exchange_segment:ids})


def market_quote(mapping, cache_seconds=10):
    global _QUOTE_CACHE,_QUOTE_CACHE_AT
    if mapping is None or mapping.empty or not configured(): return pd.DataFrame()
    now=time.monotonic()
    with _LOCK:
        if _QUOTE_CACHE and now-_QUOTE_CACHE_AT<=cache_seconds: return pd.DataFrame(list(_QUOTE_CACHE.values()))
    ids=pd.to_numeric(mapping["SecurityId"],errors="coerce").dropna().astype(int).astype(str).tolist(); response=_marketfeed("NSE_EQ",ids)
    data=response.get("data",{}).get("NSE_EQ",{}) if response else {}; by_id=dict(zip(mapping["SecurityId"].astype(str),mapping["Symbol"].astype(str))); rows=[]
    for sid,item in data.items():
        if not isinstance(item,dict): continue
        o=item.get("ohlc") or {}
        try:
            ltp=float(item.get("last_price") or 0); nc=float(item.get("net_change") or 0); prev=ltp-nc if ltp>0 else 0
            rows.append({"Symbol":by_id.get(str(sid),str(sid)),"SecurityId":str(sid),"LTP":ltp,"TodayOpen":float(o.get("open") or 0),"TodayHigh":float(o.get("high") or 0),"TodayLow":float(o.get("low") or 0),"TodayClose":float(o.get("close") or 0),"PreviousClose":prev,"NetChange":nc,"Volume":float(item.get("volume") or 0),"UpdatedAt":datetime.now().isoformat(timespec="seconds")})
        except (TypeError,ValueError): pass
    _set_status(received=len(rows),requested=len(ids),ok=len(rows)>0,stage="/marketfeed/quote",message=f"Received {len(rows)}/{len(ids)} quotes" if rows else _LAST_DHAN_STATUS.get("message","No quotes returned"))
    result=pd.DataFrame(rows)
    if not result.empty:
        with _LOCK: _QUOTE_CACHE={str(r["Symbol"]):r.to_dict() for _,r in result.iterrows()}; _QUOTE_CACHE_AT=time.monotonic()
    return result


def index_quote(index_name="NIFTY 500"):
    m=load_instrument_master()
    if m.empty or not configured(): return None
    nc=_col(m,("SEM_CUSTOM_SYMBOL","SM_CUSTOM_SYMBOL","DISPLAY_NAME","SYMBOL_NAME")); ic=_col(m,("SEM_SECURITY_ID","SECURITY_ID")); seg=_col(m,("SEM_SEGMENT","SEGMENT")); ins=_col(m,("SEM_INSTRUMENT_NAME","INSTRUMENT"))
    if not nc or not ic: return None
    x=m.copy(); x["_name"]=x[nc].astype(str).str.strip().str.upper(); mask=x["_name"].eq(index_name.upper())
    if not mask.any(): mask=x["_name"].str.contains(index_name.upper(),regex=False,na=False)
    if seg: mask &= x[seg].astype(str).str.upper().eq("I")
    if ins: mask &= x[ins].astype(str).str.upper().eq("INDEX")
    match=x.loc[mask]
    if match.empty: return None
    sid=str(match.iloc[0][ic]).strip(); response=_marketfeed("IDX_I",[sid]); item=(response.get("data",{}).get("IDX_I",{}) if response else {}).get(sid)
    if not isinstance(item,dict): return None
    o=item.get("ohlc") or {}
    try:
        ltp=float(item.get("last_price") or 0); nc=float(item.get("net_change") or 0); prev=ltp-nc if ltp>0 else 0
        return {"LTP":ltp,"Open":float(o.get("open") or 0),"High":float(o.get("high") or 0),"Low":float(o.get("low") or 0),"Close":float(o.get("close") or 0),"PreviousClose":prev,"NetChange":nc,"SecurityId":sid}
    except (TypeError,ValueError): return None


def daily_history(security_id, from_date, to_date):
    response=_post("/charts/historical",{"securityId":str(security_id),"exchangeSegment":"NSE_EQ","instrument":"EQUITY","expiryCode":0,"oi":False,"fromDate":from_date,"toDate":to_date},timeout=20)
    if not response: return pd.DataFrame()
    try:
        x=pd.DataFrame({"Open":response.get("open",[]),"High":response.get("high",[]),"Low":response.get("low",[]),"Close":response.get("close",[]),"Volume":response.get("volume",[]),"Timestamp":response.get("timestamp",[])})
        if x.empty:return x
        x["Datetime"]=pd.to_datetime(x["Timestamp"],unit="s",utc=True).dt.tz_convert(IST); return x.drop(columns=["Timestamp"]).sort_values("Datetime").reset_index(drop=True)
    except Exception: return pd.DataFrame()


def previous_day_references(mapping, force=False):
    if mapping is None or mapping.empty or not configured(): return pd.DataFrame()
    today=datetime.now().date(); rows=[]; fd=(today-timedelta(days=10)).isoformat(); td=(today+timedelta(days=1)).isoformat()
    for _,item in mapping.iterrows():
        h=daily_history(str(item["SecurityId"]),fd,td)
        if h.empty: continue
        prior=h[h["Datetime"].dt.date<today]
        if prior.empty: continue
        r=prior.iloc[-1]; rows.append({"Symbol":str(item["Symbol"]),"SecurityId":str(item["SecurityId"]),"PDH":float(r["High"]),"PDL":float(r["Low"]),"PreviousDayClose":float(r["Close"]),"PreviousDayOpen":float(r["Open"]),"PreviousDayVolume":float(r.get("Volume",0) or 0)})
    return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
