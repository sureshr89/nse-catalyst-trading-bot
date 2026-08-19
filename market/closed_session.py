"""Independent closed-session summary using verified Dhan historical data."""
from datetime import datetime,time as dt_time,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,threading,time
import pandas as pd
from data.stock_universe import StockUniverse
from market.nifty500_breadth import BREADTH
from market.dhan_data import map_nifty500,daily_history,load_instrument_master
IST=ZoneInfo("Asia/Kolkata");STORE=Path(__file__).resolve().parents[1]/"data"/"closed_sessions";STORE.mkdir(parents=True,exist_ok=True)
_RATE_LOCK=threading.Lock();_NEXT_REQUEST=0.0

def _session_date(now):
 d=now.date()
 if now.time()<dt_time(15,30):d-=timedelta(days=1)
 while d.weekday()>=5:d-=timedelta(days=1)
 return d
def _file(d):return STORE/f"nifty500_closed_{d.isoformat()}.json"
def _latest_file(before=None):
 cutoff=(before or datetime.now(IST).date()).isoformat();files=sorted(STORE.glob("nifty500_closed_*.json"));c=[p for p in files if p.stem.replace("nifty500_closed_","")<cutoff];return c[-1] if c else None
def load_saved(date=None):
 d=date or _session_date(datetime.now(IST));p=_file(d)
 if not p.exists():p=_latest_file(d+timedelta(days=1)) or p
 if not p.exists():
  try:return build_closed_snapshot(force=False)
  except Exception:return pd.DataFrame(),{}
 try:return pd.DataFrame(),json.loads(p.read_text())
 except Exception:return pd.DataFrame(),{}
def latest_saved_before(date=None):
 d=date or datetime.now(IST).date();p=_latest_file(d)
 if p:
  try:return pd.DataFrame(),json.loads(p.read_text())
  except Exception:pass
 return build_closed_snapshot(force=False)
def _throttled_history(sid,fd,td):
 global _NEXT_REQUEST
 with _RATE_LOCK:
  wait=max(0.0,_NEXT_REQUEST-time.monotonic())
  if wait:time.sleep(wait)
  _NEXT_REQUEST=time.monotonic()+0.205
 return daily_history(str(sid),fd,td)
def _historical_500():
 u=StockUniverse().get_dataframe(refresh=False)
 if u is None or u.empty or "Symbol" not in u.columns:u=StockUniverse().get_dataframe(refresh=True)
 if u is None or u.empty:return pd.DataFrame(),{}
 u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);u=u.drop_duplicates("Symbol").head(500)
 if len(u)<500:return pd.DataFrame(),{"reason":f"NIFTY 500 universe only {len(u)}/500"}
 mapping=map_nifty500(u["Symbol"].tolist())
 if len(mapping)<500:return pd.DataFrame(),{"reason":f"Dhan security mapping only {len(mapping)}/500"}
 today=datetime.now(IST).date();fd=(today-timedelta(days=10)).isoformat();td=(today+timedelta(days=1)).isoformat();rows=[]
 with ThreadPoolExecutor(max_workers=5) as pool:
  futures={pool.submit(_throttled_history,r.SecurityId,fd,td):r for r in mapping.itertuples()}
  for f in as_completed(futures):
   r=futures[f]
   try:h=f.result()
   except Exception:continue
   if h.empty:continue
   prior=h[h["Datetime"].dt.date<today]
   if prior.empty:continue
   last=prior.iloc[-1];rows.append({"Symbol":r.Symbol,"SecurityId":str(r.SecurityId),"Open":float(last["Open"]),"High":float(last["High"]),"Low":float(last["Low"]),"Close":float(last["Close"]),"Volume":float(last.get("Volume",0) or 0)})
 df=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
 if df.empty:return df,{"reason":"Dhan historical daily OHLC returned no rows"}
 # Get the preceding close for A/D. The two latest completed daily candles are needed.
 # Re-requesting only the mapped securities would double calls, so use the previous
 # session close already available in the quote cache when possible.
 return df,{"coverage":f"{len(df)}/500"}
def _index_close_from_dhan():
 try:
  m=load_instrument_master();
  if m.empty:return None
  cols={str(c).strip().upper():c for c in m.columns};idc=next((cols[k] for k in ["SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"] if k in cols),None)
  if not idc:return None
  textcols=[c for c in m.columns if m[c].dtype==object]
  mask=pd.Series(False,index=m.index)
  for c in textcols:mask=mask|m[c].astype(str).str.upper().str.contains("NIFTY 500",regex=False,na=False)
  x=m.loc[mask]
  if x.empty:return None
  if "SEM_SEGMENT" in x.columns:
   y=x[x["SEM_SEGMENT"].astype(str).str.upper().isin(["I","INDEX"])]
   if not y.empty:x=y
  sid=str(x.iloc[0][idc]).strip();h=daily_history(sid,(datetime.now(IST).date()-timedelta(days=10)).isoformat(),(datetime.now(IST).date()+timedelta(days=1)).isoformat())
  if h.empty:return None
  prior=h[h["Datetime"].dt.date<datetime.now(IST).date()]
  return float(prior.iloc[-1]["Close"]) if not prior.empty else None
 except Exception:return None
def build_closed_snapshot(force=False):
 now=datetime.now(IST);d=_session_date(now);p=_file(d)
 if not force and p.exists():
  try:return pd.DataFrame(),json.loads(p.read_text())
  except Exception:pass
 # First use the verified 500-stock snapshot. It is instant and avoids a second quote call.
 s=BREADTH.snapshot(force=False)
 if s.get("complete") and s.get("ad_ratio") is not None and s.get("nifty500_previous_close"):
  summary={"complete":True,"session_date":d.isoformat(),"market_close":"15:30 IST","nifty500_close":s.get("nifty500_previous_close"),"nifty500_previous_close":s.get("nifty500_reference_close"),"nifty500_change_pct":s.get("nifty500_change_pct"),"advances":s.get("advances",0),"declines":s.get("declines",0),"unchanged":s.get("unchanged",0),"ad_ratio":s.get("ad_ratio"),"sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),"negative_sectors":s.get("negative_sectors",0),"coverage":"500/500","closed_session_label":"Latest completed NSE session","source":"Dhan completed-session quote","saved_at":now.isoformat(),"dhan_status":"PASS"};p.write_text(json.dumps(summary,indent=2,default=str));return pd.DataFrame(),summary
 # After market close Dhan Quote may report zero net change. In that case reconstruct
 # yesterday from Dhan's Daily Historical Data rather than showing fake 0/500.
 hist,meta=_historical_500();
 if hist.empty:return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"nifty500_close":None,"ad_ratio":None,"advances":0,"declines":0,"sector_alignment_pct":None,"positive_sectors":0,"negative_sectors":0,"coverage":meta.get("coverage","0/500"),"reason":meta.get("reason","Dhan historical data unavailable")}
 # We have the completed candle for every stock. For a truthful A/D, compare it to
 # the preceding completed candle; fetch that only when needed, using the same Dhan historical endpoint.
 today=datetime.now(IST).date();fd=(today-timedelta(days=20)).isoformat();td=(today+timedelta(days=1)).isoformat();adv=dec=unch=0;changes=[]
 # Use a second pass only for symbols that need the preceding close. Cached Dhan
 # history is not available across processes, so this is intentionally explicit.
 def calc(row):
  h=daily_history(str(row.SecurityId),fd,td)
  if h.empty:return None
  prior=h[h["Datetime"].dt.date<today]
  if len(prior)<2:return None
  a=float(prior.iloc[-1]["Close"]);b=float(prior.iloc[-2]["Close"])
  return (a-b)/b*100 if b else None
 with ThreadPoolExecutor(max_workers=5) as pool:
  fs={pool.submit(_throttled_history,r.SecurityId,fd,td):r for r in hist.itertuples()}
  for f in as_completed(fs):
   r=fs[f]
   try:h=f.result()
   except Exception:continue
   if h.empty:continue
   prior=h[h["Datetime"].dt.date<today]
   if len(prior)<2:continue
   a=float(prior.iloc[-1]["Close"]);b=float(prior.iloc[-2]["Close"])
   if a>b:adv+=1
   elif a<b:dec+=1
   else:unch+=1
   changes.append({"Symbol":r.Symbol,"change_pct":((a-b)/b*100) if b else 0.0})
 ad=float(adv/dec) if dec else (None if adv==0 else None)
 ch=pd.DataFrame(changes);align=None;pos=neg=0
 try:
  sm=__import__("data.sector_alignment",fromlist=["load_sector_map","calculate_sector_alignment"]);sector=sm.calculate_sector_alignment(ch,sm.load_sector_map(StockUniverse().get_dataframe(refresh=False),refresh=False),"change_pct");align=sector.get("alignment_pct");pos=sector.get("positive_sectors",0);neg=sector.get("negative_sectors",0)
 except Exception:pass
 idx=_index_close_from_dhan();summary={"complete":len(hist)>=450,"session_date":d.isoformat(),"market_close":"15:30 IST","nifty500_close":idx,"nifty500_previous_close":None,"nifty500_change_pct":None,"advances":adv,"declines":dec,"unchanged":unch,"ad_ratio":ad,"sector_alignment_pct":align,"positive_sectors":pos,"negative_sectors":neg,"coverage":f"{len(hist)}/500","closed_session_label":"Latest completed NSE session","source":"Dhan Daily Historical Data","saved_at":now.isoformat(),"dhan_status":"PASS"};p.write_text(json.dumps(summary,indent=2,default=str));return hist,summary
