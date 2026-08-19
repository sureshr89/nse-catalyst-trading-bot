"""Independent closed-session summary. Reuses the verified NIFTY 500 Dhan snapshot."""
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from market.nifty500_breadth import BREADTH

IST=ZoneInfo("Asia/Kolkata")
STORE=Path(__file__).resolve().parents[1]/"data"/"closed_sessions"
STORE.mkdir(parents=True,exist_ok=True)

def _session_date(now):
    d=now.date()
    if now.time()<dt_time(15,30): d-=timedelta(days=1)
    while d.weekday()>=5: d-=timedelta(days=1)
    return d

def _file(d): return STORE/f"nifty500_closed_{d.isoformat()}.json"

def load_saved(date=None):
    d=date or datetime.now(IST).date(); p=_file(d)
    if not p.exists(): return pd.DataFrame(),{}
    try:
        s=json.loads(p.read_text()); return pd.DataFrame(),s
    except Exception:return pd.DataFrame(),{}

def latest_saved_before(date=None):
    d=date or datetime.now(IST).date(); files=sorted(STORE.glob("nifty500_closed_*.json")); candidates=[]
    for p in files:
        x=p.stem.replace("nifty500_closed_","")
        if x<d.isoformat(): candidates.append(x)
    if candidates:return load_saved(datetime.fromisoformat(candidates[-1]).date())
    return build_closed_snapshot(force=True)

def build_closed_snapshot(force=False):
    now=datetime.now(IST); d=_session_date(now)
    # The breadth engine already makes the single batched Dhan 500-stock request.
    # Reuse it here so the closed section cannot trigger a second rate-limited request.
    s=BREADTH.snapshot(force=force)
    if not s.get("complete"):
        return pd.DataFrame(),{
            "complete":False,"session_date":d.isoformat(),"nifty500_close":None,
            "ad_ratio":s.get("ad_ratio"),"advances":s.get("advances",0),"declines":s.get("declines",0),
            "sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),
            "negative_sectors":s.get("negative_sectors",0),"coverage":s.get("sector_coverage",f"{s.get('evaluated',0)}/500"),
            "reason":s.get("reason","Dhan closed-session data unavailable"),"dhan_status":s.get("reason"),"source":"Dhan"
        }
    # In closed mode, nifty500_previous_close is the completed session close according to the breadth engine.
    close=s.get("nifty500_previous_close")
    summary={
        "complete":True,"session_date":d.isoformat(),"market_close":"15:30 IST",
        "nifty500_close":close,"nifty500_previous_close":s.get("nifty500_reference_close"),
        "nifty500_change_pct":s.get("nifty500_change_pct"),"advances":s.get("advances",0),
        "declines":s.get("declines",0),"unchanged":s.get("unchanged",0),"ad_ratio":s.get("ad_ratio"),
        "sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),
        "negative_sectors":s.get("negative_sectors",0),"coverage":"500/500",
        "source":"Dhan completed-session quote","saved_at":now.isoformat(),"dhan_status":"PASS"
    }
    _file(d).write_text(json.dumps(summary,indent=2,default=str))
    return pd.DataFrame(),summary
