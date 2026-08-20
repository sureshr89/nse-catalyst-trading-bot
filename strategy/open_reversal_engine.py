from __future__ import annotations
from datetime import datetime
from strategy.contracts import STRATEGY_VERSION
try:
    from market.live_price import LIVE as _LIVE
except Exception:
    class _FallbackLive:
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {}
    _LIVE = _FallbackLive()

class OpenReversalEngine:
    strategy_id="STRATEGY_1"; strategy_version=STRATEGY_VERSION
    def __init__(self,start_time="09:45",end_time="14:00",rr=1.25): self.start_time=start_time; self.end_time=end_time; self.rr=float(rr)
    def latest_completed(self,data):
        if data is None or len(data)<1:return None
        import pandas as pd
        x=data.copy();x["Datetime"]=pd.to_datetime(x["Datetime"],errors="coerce")
        now=datetime.now(x["Datetime"].iloc[0].tzinfo) if getattr(x["Datetime"].iloc[0],"tzinfo",None) else datetime.now()
        completed=x[x["Datetime"]<now];return completed.iloc[-1] if not completed.empty else x.iloc[-1]
    def build_signal(self,symbol,side,entry,reference,open_price,stop_reference,nifty_change_pct):
        entry=float(entry);stop_reference=float(stop_reference)
        if side=="BUY": stop=stop_reference;target=entry+(entry-stop)*self.rr
        else: stop=stop_reference;target=entry-(stop-entry)*self.rr
        return {"strategy":self.strategy_id,"strategy_version":self.strategy_version,"symbol":symbol,"signal":side,"entry":entry,"stop_loss":stop,"target":target,"risk_reward":self.rr,"entry_source":"LIVE_LTP"}
    def update_state(self,state,pdh,pdl,open_price,price=None):
        state=dict(state);live=_LIVE.get_latest_live_price(state.get("symbol",""),max_age_seconds=2) or {}
        if live: price=live.get("Close")
        if price is None:return state
        price=float(price);open_price=float(open_price);pdh=float(pdh);pdl=float(pdl);side=str(state.get("side","")).upper()
        if side=="BUY":
            if price < pdh and price < open_price: state["pdh_breached"]=True
            if state.get("pdh_breached") and price >= open_price: state["open_returned"]=True
        elif side=="SELL":
            if price > pdl and price > open_price: state["pdl_breached"]=True
            if state.get("pdl_breached") and price <= open_price: state["open_returned"]=True
        return state
    def build(self,*args,**kwargs): return None
    def initial_side(self,*args,**kwargs):
        try:
            o,pdh,pdl=args[:3]
            if float(o)>float(pdh):return "BUY"
            if float(o)<float(pdl):return "SELL"
        except Exception:pass
        return None
