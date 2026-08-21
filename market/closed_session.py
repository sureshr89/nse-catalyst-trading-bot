"""Independent closed-session summary using Dhan daily historical data."""
from datetime import datetime,time as dt_time,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,threading,time
import pandas as pd
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map,calculate_sector_alignment
from market.nifty500_breadth import BREADTH
from market.dhan_data import map_nifty500,daily_history,load_instrument_master
IST=ZoneInfo("Asia/Kolkata");STORE=Path(__file__).resolve().parents[1]/"data"/"closed_sessions";STORE.mkdir(parents=True,exist_ok=True);_RATE_LOCK=threading.Lock();_NEXT_REQUEST=0.0

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

def build_closed_snapshot(force=False):
 now=datetime.now(IST);d=_session_date(now);p=_file(d)
 if not force and p.exists():
  try:return pd.DataFrame(),json.loads(p.read_text())
  except Exception:pass
 s=BREADTH.snapshot(force=False)
 # Only use the live breadth shortcut after the NSE session has actually closed.
 # Before 15:30, a complete live snapshot is still an in-progress session and
 # must never be persisted/labeled as a completed-session result.
 if now.time()>=dt_time(15,30) and s.get("complete") and s.get("ad_ratio") is not None and s.get("nifty500_previous_close"):
  summary={"complete":True,"session_date":d.isoformat(),"market_close":"15:30 IST","nifty500_close":s.get("nifty500_previous_close"),"nifty500_previous_close":s.get("nifty500_reference_close"),"nifty500_change_pct":s.get("nifty500_change_pct"),"advances":s.get("advances",0),"declines":s.get("declines",0),"unchanged":s.get("unchanged",0),"ad_ratio":s.get("ad_ratio"),"sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),"negative_sectors":s.get("negative_sectors",0),"coverage":"500/500","closed_session_label":"Latest completed NSE session","source":"Dhan completed-session quote","saved_at":now.isoformat(),"dhan_status":"PASS"};p.write_text(json.dumps(summary,indent=2,default=str));return pd.DataFrame(),summary
 u=StockUniverse().get_dataframe(refresh=False)
 if u is None or u.empty or "Symbol" not in u.columns:u=StockUniverse().get_dataframe(refresh=True)
 if u is None or u.empty:return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"reason":"NIFTY_500_UNIVERSE unavailable","coverage":"0/500"}
 u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);u=u.drop_duplicates("Symbol")
 if len(u)!=500:return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"reason":f"NIFTY_500_UNIVERSE incomplete: {len(u)}/500","coverage":f"{len(u)}/500"}
 mapping=map_nifty500(u["Symbol"].tolist())
 if len(mapping)!=500:return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"reason":f"NIFTY_500_UNIVERSE Dhan mapping incomplete: {len(mapping)}/500","coverage":f"{len(mapping)}/500"}
 today=datetime.now(IST).date();fd=(today-timedelta(days=10)).isoformat();td=(today+timedelta(days=1)).isoformat();rows=[]
 with ThreadPoolExecutor(max_workers=5) as pool:
  futures={pool.submit(_throttled_history,r.SecurityId,fd,td):r for r in mapping.itertuples()}
  for f in as_completed(futures):
   r=futures[f]
   try:h=f.result()
   except Exception:continue
   if h.empty:continue
   prior=h[h["Datetime"].dt.date<today]
   if len(prior)<2:continue
   last=prior.iloc[-1];prev=prior.iloc[-2];a=float(last["Close"]);b=float(prev["Close"])
   rows.append({"Symbol":r.Symbol,"SecurityId":str(r.SecurityId),"Close":a,"PreviousClose":b,"change_pct":((a-b)/b*100) if b else 0.0,"Open":float(last["Open"]),"High":float(last["High"]),"Low":float(last["Low"]),"Volume":float(last.get("Volume",0) or 0)})
 df=pd.DataFrame(rows)
 if len(df)!=500:return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"reason":f"NIFTY_500_UNIVERSE historical coverage incomplete: {len(df)}/500","coverage":f"{len(df)}/500"}
 adv=int((df.change_pct>0).sum());dec=int((df.change_pct<0).sum());unch=int((df.change_pct==0).sum());ad=float(adv/dec) if dec else None
 try:
  sm=load_sector_map(u,refresh=False);sector=calculate_sector_alignment(df[["Symbol","change_pct"]],sm,"change_pct");align=sector.get("alignment_pct");pos=sector.get("positive_sectors",0);neg=sector.get("negative_sectors",0)
 except Exception:align=None;pos=neg=0
 summary={"complete":True,"session_date":d.isoformat(),"market_close":"15:30 IST","nifty500_close":None,"nifty500_previous_close":None,"nifty500_change_pct":None,"advances":adv,"declines":dec,"unchanged":unch,"ad_ratio":ad,"sector_alignment_pct":align,"positive_sectors":pos,"negative_sectors":neg,"coverage":"500/500","closed_session_label":"Latest completed NSE session","source":"Dhan Daily Historical Data","saved_at":now.isoformat(),"dhan_status":"PASS"};p.write_text(json.dumps(summary,indent=2,default=str));return df,summary