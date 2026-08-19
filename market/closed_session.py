"""Independent post-market NIFTY 500 closed-session snapshot."""
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd

from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.dhan_data import configured, map_nifty500, market_quote, index_quote, previous_day_references, dhan_status

IST = ZoneInfo("Asia/Kolkata"); CLOSE = dt_time(15,30); ROOT=Path(__file__).resolve().parents[1]; STORE=ROOT/"data"/"closed_sessions"; STORE.mkdir(parents=True,exist_ok=True)

def _file(d): return STORE/f"nifty500_closed_{d.isoformat()}.csv"
def _summary_file(d): return STORE/f"nifty500_closed_{d.isoformat()}.json"
def load_saved(date=None):
    d=date or datetime.now(IST).date(); p=_file(d)
    if not p.exists(): return pd.DataFrame(),{}
    try:return pd.read_csv(p),json.loads(_summary_file(d).read_text()) if _summary_file(d).exists() else {}
    except Exception:return pd.DataFrame(),{}
def latest_saved_before(date=None):
    d=date or datetime.now(IST).date(); files=sorted(STORE.glob("nifty500_closed_*.csv")); candidates=[]
    for p in files:
        x=p.stem.replace("nifty500_closed_","")
        if x<d.isoformat(): candidates.append(x)
    return load_saved(datetime.fromisoformat(candidates[-1]).date()) if candidates else (pd.DataFrame(),{})

def _universe():
    u=StockUniverse().get_dataframe(refresh=False)
    if u is None or u.empty or "Symbol" not in u.columns:u=StockUniverse().get_dataframe(refresh=True)
    if u is None or u.empty:return pd.DataFrame()
    u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);return u.drop_duplicates("Symbol").head(500)

def build_closed_snapshot(force=False):
    now=datetime.now(IST)
    # Never overwrite a completed historical day with today's live data.
    if now.time()<CLOSE:return latest_saved_before(now.date())
    existing,summary=load_saved(now.date())
    if not force and len(existing)>=500:return existing,summary
    if not configured():return latest_saved_before(now.date()) if latest_saved_before(now.date())[0].shape[0] else (pd.DataFrame(),{"complete":False,"reason":"Dhan credentials not configured","dhan_status":dhan_status()})
    u=_universe()
    if len(u)!=500:return pd.DataFrame(),{"complete":False,"reason":f"NIFTY 500 universe only {len(u)}/500","dhan_status":dhan_status()}
    mapping=map_nifty500(u.Symbol.tolist())
    if len(mapping)!=500:return pd.DataFrame(),{"complete":False,"reason":f"Dhan security mapping only {len(mapping)}/500","dhan_status":dhan_status()}
    # For a closed session, explicitly use Dhan daily history for the completed day.
    refs=previous_day_references(mapping)
    if len(refs)>=500:
        out=refs.copy();out["Close"]=out["PreviousDayClose"];out["PreviousClose"]=out["PreviousDayClose"]
        out["ChangePct"]=0.0
        # Recover the session change from the prior two daily closes via history in a later refresh; retain PDH/PDL/PDC now.
        session_date=(datetime.now(IST).date()-timedelta(days=1)).isoformat()
    else:
        # Fallback: after close Dhan market quote's OHLC is the completed session.
        q=market_quote(mapping,cache_seconds=0)
        q["Close"]=pd.to_numeric(q.get("TodayClose"),errors="coerce");q["PreviousClose"]=pd.to_numeric(q.get("PreviousClose"),errors="coerce")
        out=q.dropna(subset=["Close","PreviousClose"]);out=out[(out.Close>0)&(out.PreviousClose>0)].copy();out["ChangePct"]=(out.Close-out.PreviousClose)/out.PreviousClose*100;session_date=now.date().isoformat()
    if out.empty:return pd.DataFrame(),{"complete":False,"reason":"Dhan returned no historical/closed-session prices","dhan_status":dhan_status()}
    advances=int((out.ChangePct>0).sum());declines=int((out.ChangePct<0).sum());unchanged=int((out.ChangePct==0).sum());ad=float(advances/declines) if declines else None
    try:
        sm=load_sector_map(u,refresh=False); sector=calculate_sector_alignment(out[["Symbol","ChangePct"]].rename(columns={"ChangePct":"change_pct"}),sm,"change_pct")
    except Exception as exc: sector={"available":False,"alignment_pct":None,"positive_sectors":0,"negative_sectors":0,"coverage":"0/500","error":str(exc)}
    idx=index_quote("NIFTY 500")
    summary={"complete":len(out)>=500,"session_date":session_date,"market_close":"15:30 IST","nifty500_close":(idx or {}).get("Close"),"nifty500_previous_close":(idx or {}).get("PreviousClose"),"nifty500_change_pct":(idx or {}).get("NetChange"),"advances":advances,"declines":declines,"unchanged":unchanged,"ad_ratio":ad,"sector_alignment_pct":sector.get("alignment_pct"),"positive_sectors":sector.get("positive_sectors",0),"negative_sectors":sector.get("negative_sectors",0),"coverage":f"{len(out)}/500","source":"Dhan completed-session / historical OHLC","saved_at":now.isoformat(),"dhan_status":dhan_status()}
    out.to_csv(_file(now.date()),index=False);_summary_file(now.date()).write_text(json.dumps(summary,indent=2,default=str));return out,summary
