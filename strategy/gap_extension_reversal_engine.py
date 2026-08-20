from __future__ import annotations
from datetime import datetime
import pandas as pd
from strategy.contracts import STRATEGY_VERSION
try:
    from market.live_price import LIVE as _LIVE
except Exception:
    class _FallbackLive:
        def get_latest_live_price(self,symbol,max_age_seconds=2):return {}
    _LIVE=_FallbackLive()

class GapExtensionReversalEngine:
    strategy_id="STRATEGY_2";strategy_version=STRATEGY_VERSION
    def __init__(self,start_time="09:45",end_time="14:00",rr=1.25):self.start_time=start_time;self.end_time=end_time;self.rr=float(rr)
    def evaluate(self,symbol,data,pdh,pdl,pdc,nifty_change_pct,previous_close=None,as_of=None):
        if data is None or len(data)<2:return None
        rows=data.copy().sort_values("Datetime");rows["Datetime"]=pd.to_datetime(rows["Datetime"])
        cutoff=as_of or datetime.now(rows["Datetime"].iloc[0].tzinfo) if getattr(rows["Datetime"].iloc[0],"tzinfo",None) else as_of or datetime.now()
        history=rows[rows["Datetime"]<cutoff]
        if history.empty:return None
        open_price=float(rows.iloc[0]["Open"]);day_high=float(history["High"].max());day_low=float(history["Low"].min())
        live=_LIVE.get_latest_live_price(symbol,max_age_seconds=2) or {};entry=float(live.get("Close") or 0)
        if entry<=0:return None
        nifty=float(nifty_change_pct or 0);last_close=float(history.iloc[-1]["Close"])
        if open_price>float(pdh) and float(pdc)<open_price:
            day_high=max(day_high,float(live.get("High") or entry))
            if day_high<=open_price or entry>=open_price or last_close>=float(pdh) or nifty>0.25:return None
            target=float(pdc);stop=day_high
            if target<entry<stop:return {"strategy":"STRATEGY_2","strategy_version":self.strategy_version,"strategy_id":self.strategy_id,"symbol":symbol,"signal":"SELL","entry":entry,"target":target,"stop_loss":stop,"entry_source":"LIVE_LTP"}
        if pdl is not None and open_price<float(pdl) and float(pdc)>open_price:
            day_low=min(day_low,float(live.get("Low") or entry))
            if day_low>=open_price or entry<=open_price or last_close<=open_price or nifty<-0.25:return None
            target=float(pdc);stop=day_low
            if stop<entry<target:return {"strategy":"STRATEGY_2","strategy_version":self.strategy_version,"strategy_id":self.strategy_id,"symbol":symbol,"signal":"BUY","entry":entry,"target":target,"stop_loss":stop,"entry_source":"LIVE_LTP"}
        return None
    def initial_side(self,*args,**kwargs):
        try:
            o,pdh,pdl=args[:3]
            if float(o)>float(pdh):return "SELL"
            if float(o)<float(pdl):return "BUY"
        except Exception:pass
        return None
