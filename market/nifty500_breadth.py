"""NIFTY 500 breadth and sector alignment from one shared Dhan snapshot."""
from datetime import datetime,time as dt_time
from zoneinfo import ZoneInfo
import threading,time
import pandas as pd
from config.settings import MIN_DATA_COVERAGE_COUNT,LIVE_COLLECTION_WINDOW_SECONDS
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map,calculate_sector_alignment
from market.dhan_data import configured as dhan_configured,dhan_status,map_nifty500,index_quote
from market.live_quote_bridge import market_quote_partial

INDIA_TZ=ZoneInfo("Asia/Kolkata")
CACHE_SECONDS=float(LIVE_COLLECTION_WINDOW_SECONDS)
MARKET_OPEN=dt_time(9,15)
MARKET_CLOSE=dt_time(15,30)
REQUIRED=500

class Nifty500Breadth:
 def __init__(self):
  self.universe_engine=StockUniverse();self._lock=threading.RLock();self._cached_at=0.0;self._cached=None;self._mapping=pd.DataFrame();self._mapping_at=0.0;self._universe=pd.DataFrame()
 def _get_universe(self):
  if self._universe is not None and len(self._universe)==REQUIRED and self._universe["Symbol"].nunique()==REQUIRED and "Sector" in self._universe.columns and not self._universe["Sector"].astype(str).str.upper().isin({"UNKNOWN","NAN","NONE",""}).any():return self._universe
  u=self.universe_engine.get_dataframe(refresh=False)
  valid=u is not None and not u.empty and "Symbol" in u.columns and "Sector" in u.columns and len(u)==REQUIRED and u["Symbol"].nunique()==REQUIRED
  if not valid:u=self.universe_engine.get_dataframe(refresh=True)
  if u is None or u.empty or "Symbol" not in u.columns:return pd.DataFrame()
  u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);u=u.drop_duplicates("Symbol").reset_index(drop=True)
  if "Sector" not in u.columns:u["Sector"]=u.get("Industry","UNKNOWN")
  if len(u)!=REQUIRED or u["Symbol"].nunique()!=REQUIRED or u["Sector"].astype(str).str.upper().isin({"UNKNOWN","NAN","NONE",""}).any():return pd.DataFrame()
  self._universe=u.reset_index(drop=True);return self._universe
 def _get_mapping(self,symbols):
  now=time.monotonic()
  if not self._mapping.empty and now-self._mapping_at<3600 and set(self._mapping.Symbol.astype(str).str.upper())==set(symbols):return self._mapping
  self._mapping=map_nifty500(symbols,force=False);self._mapping_at=now;return self._mapping
 @staticmethod
 def _closed_session_mode(now):return now.timetz().replace(tzinfo=None)>=MARKET_CLOSE or now.timetz().replace(tzinfo=None)<MARKET_OPEN
 def _unknown(self,reason,mode,now,evaluated=0,sector=None):
  sector=sector or {}
  return {"universe":"NIFTY 500","total":REQUIRED,"evaluated":int(evaluated),"advances":0,"declines":0,"unchanged":0,"ad_ratio":None,"direction":"UNKNOWN","complete":False,"reason":reason,"updated_at":f"{mode} • waiting for Dhan data • refreshed {now.strftime('%H:%M:%S')} IST","nifty500_change_pct":None,"nifty500_ltp":None,"nifty500_previous_close":None,"nifty500_reference_close":None,"closed_session_label":"Latest completed NSE session","closed_session_basis":"Dhan data","market_close_time":"15:30 IST","sector_alignment_pct":sector.get("alignment_pct"),"sector_complete":False,"sector_coverage":sector.get("coverage",f"{evaluated}/500"),"sector_mapped":sector.get("mapped",0),"sector_priced":sector.get("priced",0),"sector_count":sector.get("sectors",0),"positive_sectors":sector.get("positive_sectors",0),"negative_sectors":sector.get("negative_sectors",0),"unchanged_sectors":sector.get("unchanged_sectors",0),"sector_error":sector.get("error"),"market_data_source":"DHAN" if dhan_configured() else "UNCONFIGURED","quote_rows":pd.DataFrame(),"_cache_date":now.date(),"_cache_mode":mode}
 def _fail(self,reason,mode,now,evaluated=0,sector=None):return self._store(self._unknown(f"{reason} | {dhan_status().get('message') or ''}".strip(" |"),mode,now,evaluated,sector))
 def snapshot(self,force=False):
  now=datetime.now(INDIA_TZ);mode="closed" if self._closed_session_mode(now) else "live";mono=time.monotonic()
  with self._lock:
   if not force and self._cached is not None and now.date()==self._cached.get("_cache_date") and mode==self._cached.get("_cache_mode") and mono-self._cached_at<CACHE_SECONDS:return dict(self._cached)
  u=self._get_universe()
  if u.empty:return self._fail("NIFTY_500_UNIVERSE_NOT_EXACTLY_500",mode,now)
  symbols=u.Symbol.astype(str).str.upper().str.replace(".NS","",regex=False).drop_duplicates().tolist()
  if len(symbols)!=REQUIRED:return self._fail(f"NIFTY_500_UNIVERSE_ONLY_{len(symbols)}/500",mode,now,len(symbols))
  if not dhan_configured():return self._fail("DHAN_NOT_CONFIGURED",mode,now)
  mapping=self._get_mapping(symbols)
  if mapping.empty:return self._fail("DHAN_SECURITY_MAPPING_EMPTY",mode,now)
  if len(mapping)<MIN_DATA_COVERAGE_COUNT:return self._fail(f"DHAN_SECURITY_MAPPING_BELOW_98PCT_{len(mapping)}/500",mode,now,len(mapping))

  # One shared 15-second collection window. Valid prices are merged by Symbol;
  # no strategy/dashboard component performs another 500-stock request.
  quotes=market_quote_partial(mapping)
  if quotes.empty:return self._fail("DHAN_QUOTES_UNAVAILABLE",mode,now,0)
  for c in ["LTP","PreviousClose","TodayClose"]:
   if c in quotes.columns:quotes[c]=pd.to_numeric(quotes[c],errors="coerce")
  if "TodayClose" not in quotes.columns:quotes["TodayClose"]=quotes["LTP"]
  quotes["SessionClose"]=quotes["TodayClose"] if mode=="closed" else quotes["LTP"]
  quotes=quotes.dropna(subset=["SessionClose","PreviousClose"]);quotes=quotes[(quotes.SessionClose>0)&(quotes.PreviousClose>0)].drop_duplicates("Symbol")
  coverage=len(quotes)
  quotes["change_pct"]=(quotes.SessionClose-quotes.PreviousClose)/quotes.PreviousClose*100
  delta=quotes.SessionClose-quotes.PreviousClose;tolerance=quotes.PreviousClose.abs()*1e-10
  advances=int((delta>tolerance).sum());declines=int((delta<-tolerance).sum());unchanged=int(coverage-advances-declines);ad_ratio=advances/declines if declines else None

  try:
   sm=load_sector_map(u,refresh=True);sector=calculate_sector_alignment(quotes[["Symbol","change_pct"]],sm,"change_pct")
  except Exception as exc:
   sector={"available":False,"alignment_pct":None,"mapped":0,"priced":0,"sectors":0,"positive_sectors":0,"negative_sectors":0,"unchanged_sectors":0,"coverage":f"{coverage}/500","error":str(exc)}
  sector_priced=int(sector.get("priced",0) or 0)
  sector_complete=bool(sector.get("available")) and sector_priced>=MIN_DATA_COVERAGE_COUNT

  try:nifty=index_quote("NIFTY 500")
  except Exception:nifty=None
  if not nifty:return self._fail("DHAN_NIFTY_500_INDEX_QUOTE_UNAVAILABLE",mode,now,coverage,sector)
  prev_close=float(nifty.get("PreviousClose") or 0);live_ltp=float(nifty.get("LTP") or 0);day_close=float(nifty.get("Close") or 0)
  if prev_close<=0 or live_ltp<=0:return self._fail("DHAN_NIFTY_500_INDEX_INVALID_PRICE",mode,now,coverage,sector)
  if mode=="closed":session_close=day_close if day_close>0 else live_ltp;nifty_change=(session_close-prev_close)/prev_close*100;display_close=session_close;label="Latest completed NSE session"
  else:nifty_change=(live_ltp-prev_close)/prev_close*100;display_close=prev_close;label="Previous completed NSE session"

  complete=coverage>=MIN_DATA_COVERAGE_COUNT
  result={"universe":"NIFTY 500","total":REQUIRED,"evaluated":coverage,"advances":advances,"declines":declines,"unchanged":unchanged,"ad_ratio":ad_ratio,"direction":"BULLISH" if advances>declines else "BEARISH" if declines>advances else "NEUTRAL","complete":complete,"reason":"OK" if complete else f"BELOW_98PCT_{coverage}/500","updated_at":f"{label} • refreshed {now.strftime('%H:%M:%S')} IST","nifty500_change_pct":nifty_change,"nifty500_ltp":live_ltp,"nifty500_previous_close":display_close,"nifty500_reference_close":prev_close,"closed_session_label":label,"closed_session_basis":"Dhan completed-session close" if mode=="closed" else "Dhan live LTP","market_close_time":"15:30 IST","sector_alignment_pct":sector.get("alignment_pct"),"sector_complete":sector_complete,"sector_coverage":sector.get("coverage",f"{sector_priced}/500"),"sector_mapped":int(sector.get("mapped",0) or 0),"sector_priced":sector_priced,"sector_count":sector.get("sectors",0),"positive_sectors":sector.get("positive_sectors",0),"negative_sectors":sector.get("negative_sectors",0),"unchanged_sectors":sector.get("unchanged_sectors",0),"sector_error":sector.get("error"),"market_data_source":"DHAN","quote_rows":quotes.copy(),"_cache_date":now.date(),"_cache_mode":mode}
  return self._store(result)
 def _store(self,result):
  with self._lock:self._cached=result;self._cached_at=time.monotonic()
  return dict(result)
 def allows(self,side):
  s=self.snapshot();side=str(side).upper()
  if not s.get("complete") or not s.get("sector_complete"):return False,s
  n,sec,ad=s.get("nifty500_change_pct"),s.get("sector_alignment_pct"),s.get("ad_ratio")
  if side=="BUY":return bool(n is not None and n>0 and sec is not None and sec>0 and ad is not None and ad>1),s
  if side=="SELL":return bool(n is not None and n<0 and sec is not None and sec<0 and ad is not None and ad<1),s
  return False,s
BREADTH=Nifty500Breadth()
