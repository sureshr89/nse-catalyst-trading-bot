"""Independent closed-session summary. Reuses the verified NIFTY 500 Dhan snapshot."""
from datetime import datetime,time as dt_time,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from market.nifty500_breadth import BREADTH
IST=ZoneInfo("Asia/Kolkata");STORE=Path(__file__).resolve().parents[1]/"data"/"closed_sessions";STORE.mkdir(parents=True,exist_ok=True)
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
 # Dashboard historically passed today's date after midnight. If today's file does
 # not exist, automatically return the latest completed NSE session instead.
 if not p.exists():
  p=_latest_file(d+timedelta(days=1)) or p
 if not p.exists():
  try:return build_closed_snapshot(force=False)
  except Exception:return pd.DataFrame(),{}
 try:s=json.loads(p.read_text());return pd.DataFrame(),s
 except Exception:return pd.DataFrame(),{}
def latest_saved_before(date=None):
 d=date or datetime.now(IST).date();p=_latest_file(d)
 if p:
  try:s=json.loads(p.read_text());return pd.DataFrame(),s
  except Exception:pass
 return build_closed_snapshot(force=False)
def build_closed_snapshot(force=False):
 now=datetime.now(IST);d=_session_date(now)
 if not force:
  existing=_file(d)
  if existing.exists():
   try:return pd.DataFrame(),json.loads(existing.read_text())
   except Exception:pass
 s=BREADTH.snapshot(force=force)
 if not s.get("complete"):
  return pd.DataFrame(),{"complete":False,"session_date":d.isoformat(),"nifty500_close":s.get("nifty500_previous_close"),"ad_ratio":s.get("ad_ratio"),"advances":s.get("advances",0),"declines":s.get("declines",0),"sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),"negative_sectors":s.get("negative_sectors",0),"coverage":f"{s.get('evaluated',0)}/500","reason":s.get("reason","Dhan closed-session data unavailable"),"source":"Dhan"}
 summary={"complete":True,"session_date":d.isoformat(),"market_close":"15:30 IST","nifty500_close":s.get("nifty500_previous_close"),"nifty500_previous_close":s.get("nifty500_reference_close"),"nifty500_change_pct":s.get("nifty500_change_pct"),"advances":s.get("advances",0),"declines":s.get("declines",0),"unchanged":s.get("unchanged",0),"ad_ratio":s.get("ad_ratio"),"sector_alignment_pct":s.get("sector_alignment_pct"),"positive_sectors":s.get("positive_sectors",0),"negative_sectors":s.get("negative_sectors",0),"coverage":"500/500","closed_session_label":"Latest completed NSE session","source":"Dhan completed-session quote","saved_at":now.isoformat(),"dhan_status":"PASS"}
 _file(d).write_text(json.dumps(summary,indent=2,default=str));return pd.DataFrame(),summary
