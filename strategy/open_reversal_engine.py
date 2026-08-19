"""NIFTY 500 S1 PDH/PDL + Today's Open return strategy."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import ENABLE_LONG, ENABLE_SHORT, NIFTY500_MIN_CHANGE_PCT
from strategy.contracts import STRATEGY_VERSION, STRATEGY_1_NAME
from market.price_data import PriceData
from market.nifty500_breadth import BREADTH
INDIA_TZ=ZoneInfo("Asia/Kolkata")
_LIVE=PriceData()
class OpenReversalEngine:
    strategy_id="STRATEGY_1"; strategy_name=STRATEGY_1_NAME; strategy_version=STRATEGY_VERSION
    def __init__(self,trading_start="09:45",last_entry_time="14:00",rr=1.25): self.start=self._time(trading_start); self.end=self._time(last_entry_time); self.rr=float(rr)
    @staticmethod
    def _time(value): h,m=map(int,str(value).split(":")); return time(h,m)
    @staticmethod
    def clean_prices(data):
        if data is None or data.empty or "Datetime" not in data.columns or "Close" not in data.columns:return pd.DataFrame()
        r=data.copy();r["Datetime"]=pd.to_datetime(r["Datetime"],errors="coerce")
        try:r["Datetime"]=r["Datetime"].dt.tz_localize(INDIA_TZ) if r["Datetime"].dt.tz is None else r["Datetime"].dt.tz_convert(INDIA_TZ)
        except Exception:return pd.DataFrame()
        for c in ("Open","High","Low","Close","Volume"):
            if c in r.columns:r[c]=pd.to_numeric(r[c],errors="coerce")
        return r.dropna(subset=["Datetime","Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)
    @staticmethod
    def latest_completed(data):
        p=OpenReversalEngine.clean_prices(data)
        if p.empty:return None
        m=datetime.now(INDIA_TZ).replace(second=0,microsecond=0);x=p[p["Datetime"]<m]
        return None if x.empty else x.iloc[-1]
    @staticmethod
    def previous_completed_green(data):
        c=OpenReversalEngine.latest_completed(data)
        return bool(c is not None and float(c.get("Close",0))>float(c.get("Open",0)))
    @staticmethod
    def previous_completed_red(data):
        c=OpenReversalEngine.latest_completed(data)
        return bool(c is not None and float(c.get("Close",0))<float(c.get("Open",0)))
    @staticmethod
    def completed_only(data):
        p=OpenReversalEngine.clean_prices(data)
        if p.empty:return p
        m=datetime.now(INDIA_TZ).replace(second=0,microsecond=0);return p[p["Datetime"]<m].copy()
    def initial_side(self,today_open,pdh,pdl):
        if ENABLE_LONG and float(today_open)>float(pdh):return "BUY"
        if ENABLE_SHORT and float(today_open)<float(pdl):return "SELL"
        return None
    @staticmethod
    def _live(symbol):
        try:return _LIVE.get_latest_live_price(str(symbol),max_age_seconds=2) if symbol else None
        except Exception:return None
    def update_state(self,state,today_open,pdh,pdl,completed_close=None,stamp=None):
        state=dict(state);side=str(state.get("side","")).upper();open_price,pdh,pdl=float(today_open),float(pdh),float(pdl);symbol=str(state.get("symbol","")).strip().upper();live=self._live(symbol)
        if live is None:return state
        try:ltp=float(live.get("Close"))
        except (TypeError,ValueError):return state
        if ltp<=0:return state
        now=datetime.now(INDIA_TZ).isoformat(timespec="milliseconds")
        try:
            day_low=float(live.get("Low"));old=state.get("today_low")
            if day_low>0:state["today_low"]=min(float(old),day_low) if old is not None else day_low
        except (TypeError,ValueError):pass
        try:
            day_high=float(live.get("High"));old=state.get("today_high")
            if day_high>0:state["today_high"]=max(float(old),day_high) if old is not None else day_high
        except (TypeError,ValueError):pass
        if side=="BUY":
            if not state.get("pdh_breached") and ltp<=pdh:state.update({"pdh_breached":True,"pdh_breach_time":now,"breach_price":ltp})
            if state.get("pdh_breached") and ltp>=open_price:state.update({"open_returned":True,"qualified_time":now,"qualified_ltp":ltp,"trigger_price":ltp})
        elif side=="SELL":
            if not state.get("pdl_breached") and ltp>=pdl:state.update({"pdl_breached":True,"pdl_breach_time":now,"breach_price":ltp})
            if state.get("pdl_breached") and ltp<=open_price:state.update({"open_returned":True,"qualified_time":now,"qualified_ltp":ltp,"trigger_price":ltp})
        return state
    def market_aligned(self,side,nifty_change_pct):
        try:change=float(nifty_change_pct)
        except (TypeError,ValueError):return False
        change_ok=change>NIFTY500_MIN_CHANGE_PCT if str(side).upper()=="BUY" else change< -NIFTY500_MIN_CHANGE_PCT
        ad_ok,_=BREADTH.allows(side);return change_ok and ad_ok
    def build_signal(self,symbol,side,entry,today_open,pdh,pdl,nifty_change_pct,metrics=None,today_low=None,today_high=None,previous_candle=None):
        side=str(side).upper();entry=float(entry);stop=float(today_low) if side=="BUY" else float(today_high)
        if stop<=0:return None
        risk=entry-stop if side=="BUY" else stop-entry
        if risk<=0:return None
        candle=previous_candle
        if candle is None:return None
        try:prev_open=float(candle["Open"]);prev_close=float(candle["Close"])
        except (TypeError,ValueError,KeyError):return None
        if side=="BUY" and prev_close<=prev_open:return None
        if side=="SELL" and prev_close>=prev_open:return None
        target=entry+risk*self.rr if side=="BUY" else entry-risk*self.rr
        breadth=BREADTH.snapshot()
        if not breadth.get("complete"):return None
        if side=="BUY" and breadth.get("ad_ratio",0)<=1:return None
        if side=="SELL" and breadth.get("ad_ratio",0)>=1:return None
        now=datetime.now(INDIA_TZ)
        signal={"symbol":str(symbol).upper(),"strategy":self.strategy_id,"strategy_name":self.strategy_name,"strategy_version":self.strategy_version,"signal":side,"entry_time":now.isoformat(timespec="milliseconds"),"entry":round(entry,4),"open_cross_level":round(float(today_open),4),"stop_loss":round(stop,4),"target":round(target,4),"risk_per_share":round(risk,4),"risk_reward":self.rr,"pdh":round(float(pdh),4),"pdl":round(float(pdl),4),"today_open":round(float(today_open),4),"today_low_at_entry":round(float(today_low),4),"today_high_at_entry":round(float(today_high),4),"nifty500_change_pct":round(float(nifty_change_pct),4),"nifty500_ad_ratio":breadth.get("ad_ratio"),"nifty500_advances":breadth.get("advances"),"nifty500_declines":breadth.get("declines"),"nifty500_ad_evaluated":breadth.get("evaluated"),"nifty500_ad_coverage":f"{breadth.get('evaluated',0)}/500","previous_candle_open":prev_open,"previous_candle_close":prev_close,"previous_candle_side":"GREEN" if prev_close>prev_open else "RED","entry_source":"LIVE_LTP","exit_rules":"SL or 1.25R target; mandatory 15:00 IST square-off"}
        if metrics:signal.update({k:v for k,v in metrics.items() if "atr" not in str(k).lower() and "average_true_range" not in str(k).lower()})
        return signal
    def build(self,symbol,prices,pdh,pdl,today_open=None,nifty_change_pct=0.0,nifty_candle=None):
        data=self.completed_only(prices)
        if data.empty or pdh is None or pdl is None:return None
        today=datetime.now(INDIA_TZ).date();today_data=data[data["Datetime"].dt.date==today]
        if today_data.empty:return None
        open_price=float(today_open) if today_open is not None else float(today_data.iloc[0]["Open"]);side=self.initial_side(open_price,pdh,pdl)
        if side is None or not self.market_aligned(side,nifty_change_pct):return None
        state={"symbol":symbol,"side":side,"pdh_breached":False,"pdl_breached":False,"open_returned":False};state=self.update_state(state,open_price,pdh,pdl)
        if not state.get("open_returned"):return None
        live=self._live(symbol)
        if live is None:return None
        return self.build_signal(symbol,side,float(live["Close"]),open_price,pdh,pdl,nifty_change_pct,today_low=state.get("today_low"),today_high=state.get("today_high"),previous_candle=self.latest_completed(prices))
