"""Whole-universe NIFTY 500 breadth and sector alignment."""
from datetime import datetime
from zoneinfo import ZoneInfo
import threading,time,pandas as pd
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map,calculate_sector_alignment
from market.price_data import PriceData
INDIA_TZ=ZoneInfo("Asia/Kolkata"); CACHE_SECONDS=15
class Nifty500Breadth:
    def __init__(self):
        self.universe_engine=StockUniverse();self.price_data=PriceData();self._lock=threading.RLock();self._cached_at=0.0;self._cached=None
    def snapshot(self,force=False):
        now=time.monotonic()
        with self._lock:
            if not force and self._cached is not None and now-self._cached_at<CACHE_SECONDS:return dict(self._cached)
        universe=self.universe_engine.get_dataframe(refresh=False)
        if universe is None or universe.empty or "Symbol" not in universe.columns:return self._store(self._unknown("NIFTY_500_UNIVERSE_UNAVAILABLE"))
        symbols=universe["Symbol"].astype(str).str.upper().str.replace(".NS","",regex=False).drop_duplicates().tolist()
        if len(symbols)<500:return self._store(self._unknown(f"NIFTY_500_UNIVERSE_ONLY_{len(symbols)}",len(symbols)))
        symbols=symbols[:500];intraday=self.price_data.get_multi_1m(symbols);daily=self.price_data.get_multi_daily(symbols,period="5d");today=datetime.now(INDIA_TZ).date();rows=[]
        for symbol in symbols:
            current=previous=None;frame=intraday.get(symbol)
            if isinstance(frame,pd.DataFrame) and not frame.empty:
                f=frame.copy();f["Datetime"]=pd.to_datetime(f["Datetime"],errors="coerce");f=f.dropna(subset=["Datetime"]);cur=f[f["Datetime"].dt.date==today]
                if not cur.empty:current=float(cur.iloc[-1]["Close"])
            d=daily.get(symbol)
            if isinstance(d,pd.DataFrame) and not d.empty:
                d=d.copy();d["Datetime"]=pd.to_datetime(d["Datetime"],errors="coerce");d=d.dropna(subset=["Datetime"]).sort_values("Datetime");prior=d[d["Datetime"].dt.date<today];curd=d[d["Datetime"].dt.date==today]
                if current is None and not curd.empty:current=float(curd.iloc[-1]["Close"])
                if not prior.empty:previous=float(prior.iloc[-1]["Close"])
            if current is not None and previous is not None and previous>0:rows.append({"Symbol":symbol,"current":current,"previous":previous,"change_pct":(current-previous)/previous*100})
        if len(rows)!=500:return self._store(self._unknown(f"INCOMPLETE_NIFTY_500_COVERAGE_{len(rows)}_500",len(rows)))
        prices=pd.DataFrame(rows);adv=int((prices.current>prices.previous).sum());dec=int((prices.current<prices.previous).sum());unch=int((prices.current==prices.previous).sum());ratio=float(adv/dec) if dec else float("inf")
        try:sector=calculate_sector_alignment(prices,load_sector_map(universe,refresh=False),"change_pct")
        except Exception as exc:sector={"available":False,"alignment_pct":None,"mapped":0,"priced":0,"sectors":0,"positive_sectors":0,"negative_sectors":0,"coverage":"500/500","error":str(exc)}
        return self._store({"universe":"NIFTY 500","total":500,"evaluated":500,"advances":adv,"declines":dec,"unchanged":unch,"ad_ratio":ratio,"direction":"BULLISH" if adv>dec else "BEARISH" if dec>adv else "NEUTRAL","complete":True,"reason":"OK","updated_at":datetime.now(INDIA_TZ).isoformat(timespec="seconds"),"sector_alignment_pct":sector.get("alignment_pct"),"sector_complete":bool(sector.get("available")),"sector_coverage":sector.get("coverage","0/500"),"sector_mapped":sector.get("mapped",0),"sector_priced":sector.get("priced",0),"sector_count":sector.get("sectors",0),"positive_sectors":sector.get("positive_sectors",0),"negative_sectors":sector.get("negative_sectors",0)})
    def _store(self,result):
        with self._lock:self._cached,self._cached_at=result,time.monotonic()
        return dict(result)
    @staticmethod
    def _unknown(reason,evaluated=0):return {"universe":"NIFTY 500","total":500,"evaluated":int(evaluated),"advances":0,"declines":0,"unchanged":0,"ad_ratio":None,"direction":"UNKNOWN","complete":False,"reason":reason,"updated_at":datetime.now(INDIA_TZ).isoformat(timespec="seconds"),"sector_alignment_pct":None,"sector_complete":False,"sector_coverage":f"{evaluated}/500","sector_mapped":0,"sector_priced":0,"sector_count":0,"positive_sectors":0,"negative_sectors":0}
    def allows(self,side):
        s=self.snapshot();side=str(side).upper()
        if not s.get("complete") or not s.get("sector_complete"):return False,s
        if side=="BUY":return s["ad_ratio"]>1 and s["sector_alignment_pct"]>0,s
        if side=="SELL":return s["ad_ratio"]<1 and s["sector_alignment_pct"]<0,s
        return False,s
BREADTH=Nifty500Breadth()
