"""DhanHQ-only market-data adapter for the clean S1-S5 pipeline."""
from __future__ import annotations
from datetime import datetime
from io import StringIO
from pathlib import Path
import math,os,threading,time
import pandas as pd,requests
from config.settings import MIN_DATA_COVERAGE_COUNT
BASE_URL="https://api.dhan.co/v2";MASTER_URL="https://images.dhan.co/api-data/api-scrip-master.csv";MASTER_DETAILED_URL="https://images.dhan.co/api-data/api-scrip-master-detailed.csv";CACHE_DIR=Path("data");MASTER_CACHE=CACHE_DIR/"dhan_scrip_master.csv";IST="Asia/Kolkata";_LOCK=threading.RLock();_QUOTE_API_LOCK=threading.Lock();_LAST_QUOTE_API_AT=0.0;_QUOTE_CACHE={};_QUOTE_CACHE_AT=0.0;_QUOTE_CACHE_KEY=None;_LAST_DHAN_STATUS={"ok":False,"stage":"NOT_TESTED","http_status":None,"error_code":None,"message":"Not tested","received":0,"requested":0,"updated_at":None}
def _secret(name):
 value=os.getenv(name,"")
 if value:return str(value).strip()
 try:
  import streamlit as st;return str(st.secrets.get(name,"")).strip()
 except Exception:return ""
def configured():return bool(_secret("DHAN_CLIENT_ID") and _secret("DHAN_ACCESS_TOKEN"))
def dhan_status():return dict(_LAST_DHAN_STATUS)
def _set_status(**kwargs):
 global _LAST_DHAN_STATUS;_LAST_DHAN_STATUS={**_LAST_DHAN_STATUS,**kwargs,"updated_at":datetime.now().isoformat(timespec="seconds")}
def _headers():return {"Accept":"application/json","Content-Type":"application/json","access-token":_secret("DHAN_ACCESS_TOKEN"),"client-id":_secret("DHAN_CLIENT_ID")}
def _post(path,payload,timeout=15):
 """POST to Dhan with a process-wide quote throttle.

 DhanHQ v2 quote APIs are limited to one request/second per user. Streamlit
 fragments and the trading engine can execute in the same process, so the
 throttle must live at this shared API boundary rather than in one tab.
 """
 global _LAST_QUOTE_API_AT
 if not configured():_set_status(ok=False,stage="CONFIG",message="DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN missing");return {}
 is_quote=path.startswith("/marketfeed/")
 attempts=3 if is_quote else 1
 for attempt in range(attempts):
  try:
   if is_quote:
    with _QUOTE_API_LOCK:
     wait=max(0.0,1.10-(time.monotonic()-_LAST_QUOTE_API_AT))
     if wait:time.sleep(wait)
     r=requests.post(f"{BASE_URL}{path}",headers=_headers(),json=payload,timeout=timeout)
     _LAST_QUOTE_API_AT=time.monotonic()
   else:
    r=requests.post(f"{BASE_URL}{path}",headers=_headers(),json=payload,timeout=timeout)
   body=r.json() if r.content else {}
   if r.status_code!=200:
    code=(body.get("errorCode") or body.get("error_code") or body.get("code")) if isinstance(body,dict) else None;msg=(body.get("errorMessage") or body.get("error_message") or body.get("message")) if isinstance(body,dict) else r.text[:300]
    if is_quote and (r.status_code==429 or str(code)=="805") and attempt<attempts-1:
     time.sleep(1.5*(attempt+1));continue
    _set_status(ok=False,stage=path,http_status=r.status_code,error_code=code,message=str(msg));return {}
   _set_status(ok=True,stage=path,http_status=200,error_code=None,message="Dhan API response received");return body if isinstance(body,dict) else {}
  except Exception as exc:
   if is_quote and attempt<attempts-1:
    time.sleep(1.2*(attempt+1));continue
   _set_status(ok=False,stage=path,message=f"{type(exc).__name__}: {exc}");return {}
 return {}
def _valid_master(x):
 if x is None or x.empty:return False
 cols={str(c).strip().upper() for c in x.columns};return bool({"SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"}&cols) and bool({"SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME"}&cols)
def load_instrument_master(force=False):
 CACHE_DIR.mkdir(parents=True,exist_ok=True)
 if MASTER_CACHE.exists() and not force:
  try:
   x=pd.read_csv(MASTER_CACHE,low_memory=False)
   if _valid_master(x):return x
  except Exception:pass
 for url in (MASTER_URL,MASTER_DETAILED_URL):
  try:
   r=requests.get(url,timeout=30);r.raise_for_status();x=pd.read_csv(StringIO(r.text),low_memory=False)
   if _valid_master(x):x.to_csv(MASTER_CACHE,index=False);_set_status(stage="INSTRUMENT_MASTER",message=f"Dhan master loaded: {len(x)} rows");return x
  except Exception as exc:_set_status(ok=False,stage="INSTRUMENT_MASTER",message=f"{type(exc).__name__}: {exc}")
 return pd.DataFrame()
def _col(frame,names):
 lookup={str(c).strip().upper():c for c in frame.columns};return next((lookup[n.upper()] for n in names if n.upper() in lookup),None)
def map_nifty500(symbols,force=False):
 wanted={str(s).strip().upper().replace(".NS","") for s in symbols if str(s).strip()};m=load_instrument_master(force)
 if m.empty or not wanted:return pd.DataFrame(columns=["Symbol","SecurityId","ExchangeSegment","Instrument"])
 sc=_col(m,("SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME"));ic=_col(m,("SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"));seg=_col(m,("SEM_SEGMENT","SEGMENT"));ex=_col(m,("SEM_EXM_EXCH_ID","EXCH_ID"));ins=_col(m,("SEM_INSTRUMENT_NAME","INSTRUMENT"));ser=_col(m,("SEM_SERIES","SERIES"))
 if not sc or not ic:return pd.DataFrame(columns=["Symbol","SecurityId","ExchangeSegment","Instrument"])
 x=m.copy();x["_symbol"]=x[sc].astype(str).str.strip().str.upper().str.replace(".NS","",regex=False)
 if seg:x=x[x[seg].astype(str).str.upper().eq("E")]
 if ex:x=x[x[ex].astype(str).str.upper().eq("NSE")]
 if ser:x=x[x[ser].astype(str).str.upper().isin({"EQ","BE","BZ","SM","ST","SZ"})]
 x=x[x["_symbol"].isin(wanted)].copy();x["Symbol"]=x["_symbol"];x["SecurityId"]=pd.to_numeric(x[ic],errors="coerce");x=x.dropna(subset=["SecurityId"]);x["SecurityId"]=x["SecurityId"].astype("int64").astype(str);x["ExchangeSegment"]="NSE_EQ";x["Instrument"]=x[ins].astype(str).str.upper() if ins else "EQUITY"
 return x[x["SecurityId"].ne("")][["Symbol","SecurityId","ExchangeSegment","Instrument"]].drop_duplicates("Symbol")
def _marketfeed(exchange_segment,security_ids,endpoint="/marketfeed/ohlc"):
 normalized=[]
 for value in security_ids[:1000]:
  try:
   number=pd.to_numeric(value,errors="coerce")
   if pd.notna(number) and float(number).is_integer():normalized.append(int(number))
  except (TypeError,ValueError,OverflowError):pass
 ids=normalized;_set_status(stage=endpoint,requested=len(ids),received=0)
 if not ids:_set_status(ok=False,stage=endpoint,message="No valid numeric Dhan security IDs supplied");return {}
 return _post(endpoint,{exchange_segment:ids})
def _finite_positive(v):
 try:return math.isfinite(float(v)) and float(v)>0
 except (TypeError,ValueError):return False
def _valid_ohlc(op,hi,lo,close,ltp):return all(_finite_positive(v) for v in (op,hi,lo,close,ltp)) and hi>=max(op,lo,ltp) and lo<=min(op,hi,ltp)
def _parse_quote_response(response,mapping):
 data=response.get("data",{}).get("NSE_EQ",{}) if response else {};clean=mapping[["SecurityId","Symbol"]].copy();clean["SecurityId"]=clean["SecurityId"].astype(str);by_id=dict(zip(clean["SecurityId"],clean["Symbol"]));rows=[]
 for sid,item in data.items():
  if str(sid) not in by_id or not isinstance(item,dict):continue
  o=item.get("ohlc") or {}
  try:
   ltp=float(item.get("last_price") or 0);op=float(o.get("open") or 0);hi=float(o.get("high") or 0);lo=float(o.get("low") or 0);prev=float(o.get("close") or 0);net_raw=item.get("net_change");net=float(net_raw) if net_raw is not None else ltp-prev;vol=float(item.get("volume") or 0)
   if not _finite_positive(ltp) or not _finite_positive(prev) or not _valid_ohlc(op,hi,lo,prev,ltp) or not math.isfinite(net) or vol<0:continue
   rows.append({"Symbol":by_id[str(sid)],"SecurityId":str(sid),"LTP":ltp,"TodayOpen":op,"TodayHigh":hi,"TodayLow":lo,"TodayClose":ltp,"PreviousClose":prev,"NetChange":net,"Volume":vol,"change_pct":(ltp-prev)/prev*100.0,"UpdatedAt":datetime.now().isoformat(timespec="seconds"),"price_source":"DHAN_MARKETFEED_QUOTE"})
  except (TypeError,ValueError,OverflowError,KeyError):pass
 return pd.DataFrame(rows).drop_duplicates("SecurityId") if rows else pd.DataFrame()
def diagnostic_nifty500_live(mapping):
 if mapping is None or mapping.empty:return {"configured":configured(),"requested":0,"returned":0,"valid":0,"rows":pd.DataFrame(),"status":dhan_status(),"error":"EMPTY_MAPPING"}
 clean=mapping[["SecurityId","Symbol"]].copy();clean["SecurityId"]=pd.to_numeric(clean["SecurityId"],errors="coerce");clean=clean.dropna(subset=["SecurityId"]);clean["SecurityId"]=clean["SecurityId"].astype("int64").astype(str);clean["Symbol"]=clean["Symbol"].astype(str).str.upper().str.strip();clean=clean.drop_duplicates("Symbol")
 response=_marketfeed("NSE_EQ",clean["SecurityId"].tolist(),"/marketfeed/quote") if configured() else {}
 data=response.get("data",{}).get("NSE_EQ",{}) if response else {};rows=_parse_quote_response(response,clean);returned=len(data) if isinstance(data,dict) else 0;_set_status(received=len(rows),requested=len(clean),ok=len(rows)>0,stage="DIAGNOSTIC_QUOTE",message=f"Raw Dhan quote diagnostic: {len(rows)}/{len(clean)} valid rows")
 return {"configured":configured(),"requested":len(clean),"returned":returned,"valid":len(rows),"rows":rows,"status":dhan_status(),"error":None if len(rows)>0 else (dhan_status().get("message") or "NO_VALID_QUOTES")}
def market_quote(mapping,cache_seconds=10):
 global _QUOTE_CACHE,_QUOTE_CACHE_AT,_QUOTE_CACHE_KEY
 if mapping is None or mapping.empty or not configured() or not {"SecurityId","Symbol"}.issubset(mapping.columns):return pd.DataFrame()
 clean=mapping[["SecurityId","Symbol"]].copy();clean["SecurityId"]=pd.to_numeric(clean["SecurityId"],errors="coerce");clean=clean.dropna(subset=["SecurityId"]);clean["SecurityId"]=clean["SecurityId"].astype("int64").astype(str);clean["Symbol"]=clean["Symbol"].astype(str).str.upper().str.strip();clean=clean.drop_duplicates("SecurityId")
 if clean.empty or clean["Symbol"].duplicated().any():return pd.DataFrame()
 ids=clean["SecurityId"].tolist();expected_ids=set(ids);expected_symbols=set(clean["Symbol"]);cache_key=tuple(sorted(expected_ids));now=time.monotonic()
 with _LOCK:
  if _QUOTE_CACHE and _QUOTE_CACHE_KEY==cache_key and now-_QUOTE_CACHE_AT<=max(cache_seconds,10):
   cached=pd.DataFrame(list(_QUOTE_CACHE.values()));cached_ids=set(cached.get("SecurityId",pd.Series(dtype=str)).astype(str));cached_symbols=set(cached.get("Symbol",pd.Series(dtype=str)).astype(str).str.upper())
   if len(cached)>=MIN_DATA_COVERAGE_COUNT and cached_ids.issubset(expected_ids) and cached_symbols.issubset(expected_symbols):return cached
 response=_marketfeed("NSE_EQ",ids,"/marketfeed/quote");result=_parse_quote_response(response,clean);result_ids=set(result.get("SecurityId",pd.Series(dtype=str)).astype(str));result_symbols=set(result.get("Symbol",pd.Series(dtype=str)).astype(str).str.upper());verified=len(result)>=MIN_DATA_COVERAGE_COUNT and result_ids.issubset(expected_ids) and result_symbols.issubset(expected_symbols)
 _set_status(received=len(result),requested=len(ids),ok=verified,stage="/marketfeed/quote",message=f"Verified {len(result)}/{len(ids)} NSE_EQ quotes; minimum {MIN_DATA_COVERAGE_COUNT}/500")
 if not verified:return pd.DataFrame()
 with _LOCK:_QUOTE_CACHE={str(r["Symbol"]):r.to_dict() for _,r in result.iterrows()};_QUOTE_CACHE_AT=time.monotonic();_QUOTE_CACHE_KEY=cache_key
 return result
def index_quote(index_name="NIFTY 500"):
 if not configured():return None
 m=load_instrument_master(False)
 if m.empty:return None
 sc=_col(m,("SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME"));ic=_col(m,("SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"));seg=_col(m,("SEM_SEGMENT","SEGMENT"));ex=_col(m,("SEM_EXM_EXCH_ID","EXCH_ID"))
 if not sc or not ic:return None
 x=m.copy();x["_name"]=x[sc].astype(str).str.strip().str.upper();wanted=str(index_name).strip().upper();x=x[x["_name"].eq(wanted)]
 if seg:x=x[x[seg].astype(str).str.upper().eq("I")]
 if ex:x=x[x[ex].astype(str).str.upper().eq("NSE")]
 if x.empty:return None
 sid_raw=pd.to_numeric(x.iloc[0][ic],errors="coerce")
 if pd.isna(sid_raw) or not float(sid_raw).is_integer():return None
 sid=str(int(sid_raw));response=_post("/marketfeed/quote",{"IDX_I":[int(sid)]});item=(response.get("data",{}).get("IDX_I",{}) if response else {}).get(sid,{})
 if not isinstance(item,dict):return None
 o=item.get("ohlc") or {}
 try:
  ltp=float(item.get("last_price") or 0);close=float(o.get("close") or 0);net_raw=item.get("net_change");net=float(net_raw) if net_raw is not None else ltp-close;prev=close if _finite_positive(close) else ltp-net
  if not _finite_positive(ltp) or not _finite_positive(prev):return None
  return {"Symbol":wanted,"SecurityId":sid,"LTP":ltp,"Close":close,"PreviousClose":prev,"NetChange":net,"change_pct":(ltp-prev)/prev*100.0,"price_source":"DHAN_INDEX_QUOTE"}
 except (TypeError,ValueError,OverflowError):return None
def _history_frame(response):
 if not response:return pd.DataFrame()
 try:
  x=pd.DataFrame({"Open":response.get("open",[]),"High":response.get("high",[]),"Low":response.get("low",[]),"Close":response.get("close",[]),"Volume":response.get("volume",[]),"Timestamp":response.get("timestamp",[])})
  if x.empty:return x
  x["Datetime"]=pd.to_datetime(x["Timestamp"],unit="s",utc=True).dt.tz_convert(IST);x=x.drop(columns=["Timestamp"])
  for c in ["Open","High","Low","Close","Volume"]:x[c]=pd.to_numeric(x[c],errors="coerce")
  x=x.dropna(subset=["Open","High","Low","Close"]);return x[(x["Open"]>0)&(x["High"]>=x[["Open","Low","Close"]].max(axis=1))&(x["Low"]<=x[["Open","High","Close"]].min(axis=1))].sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)
 except Exception:return pd.DataFrame()
def intraday_history(security_id,from_dt,to_dt,interval=1):return _history_frame(_post("/charts/intraday",{"securityId":str(security_id),"exchangeSegment":"NSE_EQ","instrument":"EQUITY","interval":str(interval),"oi":False,"fromDate":from_dt,"toDate":to_dt},timeout=20))
def daily_history(security_id,from_date,to_date):return _history_frame(_post("/charts/historical",{"securityId":str(security_id),"exchangeSegment":"NSE_EQ","instrument":"EQUITY","expiryCode":0,"oi":False,"fromDate":from_date,"toDate":to_date},timeout=20))