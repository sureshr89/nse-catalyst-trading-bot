"""Independent post-market NIFTY 500 closed-session snapshot.
Live and closed-session data are intentionally separate.
"""
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import time
import pandas as pd

from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.dhan_data import configured, map_nifty500, market_quote, index_quote, dhan_status

IST=ZoneInfo("Asia/Kolkata"); CLOSE=dt_time(15,30); ROOT=Path(__file__).resolve().parents[1]; STORE=ROOT/"data"/"closed_sessions"; STORE.mkdir(parents=True,exist_ok=True)

def _file(d): return STORE/f"nifty500_closed_{d.isoformat()}.csv"
def _summary_file(d): return STORE/f"nifty500_closed_{d.isoformat()}.json"
def load_saved(date=None):
    d=date or datetime.now(IST).date(); p=_file(d)
    if not p.exists(): return pd.DataFrame(),{}
    try:return pd.read_csv(p),json.loads(_summary_file(d).read_text()) if _summary_file(d).exists() else {}
    except Exception:return pd.DataFrame(),{}
def _find_saved_before(date):
    files=sorted(STORE.glob("nifty500_closed_*.csv")); candidates=[]
    for p in files:
        x=p.stem.replace("nifty500_closed_","")
        if x<date.isoformat(): candidates.append(x)
    return load_saved(datetime.fromisoformat(candidates[-1]).date()) if candidates else (pd.DataFrame(),{})
def latest_saved_before(date=None):
    d=date or datetime.now(IST).date(); df,summary=_find_saved_before(d)
    if not df.empty:return df,summary
    return build_closed_snapshot(force=True)

def _universe():
    u=StockUniverse().get_dataframe(refresh=False)
    if u is None or u.empty or "Symbol" not in u.columns:u=StockUniverse().get_dataframe(refresh=True)
    if u is None or u.empty:return pd.DataFrame()
    u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);return u.drop_duplicates("Symbol").head(500)

def _completed_session_date(now):
    d=now.date()
    if now.time()<CLOSE:d-=timedelta(days=1)
    while d.weekday()>=5:d-=timedelta(days=1)
    return d

def build_closed_snapshot(force=False):
    now=datetime.now(IST)
    if not force:
        saved_df,saved_summary=_find_saved_before(now.date())
        if not saved_df.empty and len(saved_df)>=500:return saved_df,saved_summary
    if not configured():
        saved_df,saved_summary=_find_saved_before(now.date())
        return (saved_df,saved_summary) if not saved_df.empty else (pd.DataFrame(),{"complete":False,"reason":"Dhan credentials not configured","dhan_status":dhan_status()})
    u=_universe()
    if len(u)!=500:return pd.DataFrame(),{"complete":False,"reason":f"NIFTY 500 universe only {len(u)}/500","dhan_status":dhan_status()}
    mapping=map_nifty500(u.Symbol.tolist())
    if len(mapping)!=500:return pd.DataFrame(),{"complete":False,"reason":f"Dhan security mapping only {len(mapping)}/500","dhan_status":dhan_status()}
    q=market_quote(mapping,cache_seconds=0)
    if q.empty:return pd.DataFrame(),{"complete":False,"reason":"Dhan returned no quotes for closed-session snapshot","dhan_status":dhan_status()}
    q["Close"]=pd.to_numeric(q.get("TodayClose"),errors="coerce");q["PreviousClose"]=pd.to_numeric(q.get("PreviousClose"),errors="coerce")
    q=q.dropna(subset=["Close","PreviousClose"]);q=q[(q.Close>0)&(q.PreviousClose>0)].copy()
    if q.empty:return pd.DataFrame(),{"complete":False,"reason":"Dhan quotes contained no usable closes","dhan_status":dhan_status()}
    q["ChangePct"]=(q.Close-q.PreviousClose)/q.PreviousClose*100
    advances=int((q.ChangePct>0).sum());declines=int((q.ChangePct<0).sum());unchanged=int((q.ChangePct==0).sum());ad=float(advances/declines) if declines else None
    try:
        sm=load_sector_map(u,refresh=False);sector=calculate_sector_alignment(q[["Symbol","ChangePct"]].rename(columns={"ChangePct":"change_pct"}),sm,"change_pct")
    except Exception as exc:sector={"alignment_pct":None,"positive_sectors":0,"negative_sectors":0,"coverage":"0/500","error":str(exc)}
    # Dhan limits quote requests; wait before the separate index request.
    time.sleep(1.1)
    idx=index_quote("NIFTY 500")
    idx_close=(idx or {}).get("Close");idx_prev=(idx or {}).get("PreviousClose")
    idx_pct=((idx_close-idx_prev)/idx_prev*100) if idx_close and idx_prev else None
    session_date=_completed_session_date(now).isoformat()
    summary={"complete":len(q)>=500,"session_date":session_date,"market_close":"15:30 IST","nifty500_close":idx_close,"nifty500_previous_close":idx_prev,"nifty500_change_pct":idx_pct,"advances":advances,"declines":declines,"unchanged":unchanged,"ad_ratio":ad,"sector_alignment_pct":sector.get("alignment_pct"),"positive_sectors":sector.get("positive_sectors",0),"negative_sectors":sector.get("negative_sectors",0),"coverage":f"{len(q)}/500","source":"Dhan closed OHLC snapshot","saved_at":now.isoformat(),"dhan_status":dhan_status()}
    out=q[[c for c in ["Symbol","SecurityId","Close","PreviousClose","TodayOpen","TodayHigh","TodayLow","Volume","ChangePct"] if c in q.columns]].copy()
    out.to_csv(_file(datetime.fromisoformat(session_date).date()),index=False);_summary_file(datetime.fromisoformat(session_date).date()).write_text(json.dumps(summary,indent=2,default=str))
    return out,summary
