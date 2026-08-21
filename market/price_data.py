"""Dhan-only price data for the clean S1-S5 paper-trading pipeline."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading, time
import pandas as pd
import market.dhan_data as dhan_data

INDIA_TZ=ZoneInfo("Asia/Kolkata")

class PriceData:
    _cache_lock=threading.RLock(); _multi_1m_cache={}; _multi_1m_cache_at={}; _multi_daily_cache={}; _multi_daily_cache_at={}; _live_price_cache={}; _live_price_cache_at={}
    def __init__(self): self.valid_intervals={"1m","5m","1d"}; self.max_workers=4; self._live_price_cache=self.__class__._live_price_cache; self._live_price_cache_at=self.__class__._live_price_cache_at
    @staticmethod
    def _clean(df):
        if df is None or df.empty:return pd.DataFrame()
        x=df.copy()
        if "Datetime" not in x.columns:return pd.DataFrame()
        x["Datetime"]=pd.to_datetime(x["Datetime"],errors="coerce")
        try:x["Datetime"]=x["Datetime"].dt.tz_convert(INDIA_TZ) if x["Datetime"].dt.tz is not None else x["Datetime"].dt.tz_localize(INDIA_TZ)
        except Exception:return pd.DataFrame()
        for c in ["Open","High","Low","Close","Volume"]:
            if c in x.columns:x[c]=pd.to_numeric(x[c],errors="coerce")
        req=["Datetime","Open","High","Low","Close"]
        if any(c not in x.columns for c in req):return pd.DataFrame()
        x=x.dropna(subset=req);x=x[(x["Open"]>0)&(x["High"]>=x[["Open","Low","Close"]].max(axis=1))&(x["Low"]<=x[["Open","High","Close"]].min(axis=1))]
        return x.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)
    @staticmethod
    def _completed(df):
        x=PriceData._clean(df)
        if x.empty:return x
        cutoff=datetime.now(INDIA_TZ).replace(second=0,microsecond=0);return x[x["Datetime"]<cutoff].copy().reset_index(drop=True)
    def _today(self,df):
        x=self._clean(df);return x[x["Datetime"].dt.date==datetime.now(INDIA_TZ).date()].reset_index(drop=True) if not x.empty else x
    def _map(self,symbols):return dhan_data.map_nifty500(symbols)
    def _dhan_configured(self):return dhan_data.configured()
    def _dhan_market_quote(self,mapping):
        # Individual stock reads must not inherit the 475/500 market gate.
        # The market gate is enforced by Nifty500Breadth/strategy approval;
        # this boundary is only responsible for obtaining one live quote.
        from market.live_quote_bridge import market_quote_partial
        return market_quote_partial(mapping)
    def get_candles(self,symbol,interval="5m",period="1d"):
        if interval not in self.valid_intervals:raise ValueError(f"Unsupported interval: {interval}")
        if not dhan_data.configured():return pd.DataFrame()
        m=self._map([symbol])
        if m is None or len(m)!=1:return pd.DataFrame()
        sid=str(m.iloc[0]["SecurityId"]);now=datetime.now(INDIA_TZ);today=now.date()
        if interval=="1d":
            raw=str(period).strip().lower();days=int(raw[:-1]) if raw.endswith("d") and raw[:-1].isdigit() else 10;days=max(1,days)
            return dhan_data.daily_history(sid,(today-timedelta(days=days+5)).isoformat(),(today+timedelta(days=1)).isoformat())
        return self._completed(dhan_data.intraday_history(sid,f"{today.isoformat()} 09:00:00",now.strftime("%Y-%m-%d %H:%M:%S"),{"1m":1,"5m":5}[interval]))
    def get_1m(self,symbol):return self.get_candles(symbol,"1m","1d")
    def get_5m(self,symbol):return self.get_candles(symbol,"5m","1d")
    def get_daily(self,symbol,period="10d"):return self.get_candles(symbol,"1d",period)
    @staticmethod
    def _quote_frame(quote):
        if isinstance(quote,pd.DataFrame): return quote.copy()
        if isinstance(quote,dict):
            data=quote.get("data",quote);rows=[]
            if isinstance(data,dict):
                for items in data.values():
                    if isinstance(items,dict):
                        for security_id,item in items.items():
                            if isinstance(item,dict):
                                o=item.get("ohlc",{}) or {}
                                rows.append({"SecurityId":str(security_id),"LTP":item.get("last_price"),"TodayOpen":o.get("open"),"TodayHigh":o.get("high"),"TodayLow":o.get("low"),"PreviousClose":o.get("close"),"NetChange":item.get("net_change")})
            return pd.DataFrame(rows)
        return pd.DataFrame()
    @staticmethod
    def _normalize_live_quote(frame,security_id):
        if not isinstance(frame,pd.DataFrame) or frame.empty:return None
        x=frame.copy()
        if "SecurityId" in x.columns:
            x=x.loc[x["SecurityId"].astype(str).str.strip().eq(str(security_id).strip())]
        if x.empty:return None
        row=x.iloc[0]
        try:
            out={"Close":float(row["LTP"]),"Open":float(row["TodayOpen"]),"High":float(row["TodayHigh"]),"Low":float(row["TodayLow"]),"PreviousClose":float(row["PreviousClose"]),"NetChange":float(row["NetChange"])}
        except (KeyError,TypeError,ValueError,OverflowError):return None
        if any(pd.isna(v) or not float(v)>0 for k,v in out.items() if k!="NetChange"):return None
        if pd.isna(out["NetChange"]) or not float(out["High"])>=max(out["Open"],out["Low"],out["Close"]):return None
        if not float(out["Low"])<=min(out["Open"],out["High"],out["Close"]):return None
        return out
    def get_latest_live_price(self,symbol,max_age_seconds=8):
        key=str(symbol).upper().replace(".NS","").strip()
        if not key or not self._dhan_configured():return None
        force_fresh=max_age_seconds<=0
        if not force_fresh:
            now=time.monotonic()
            with self._cache_lock:
                cached=self._live_price_cache.get(key);age=now-self._live_price_cache_at.get(key,0)
                if cached is not None and age<=max_age_seconds:return dict(cached)
        mapping=self._map([key])
        if mapping is None or getattr(mapping,"empty",True) or len(mapping)!=1:return None
        security_id=str(mapping.iloc[0]["SecurityId"]).strip()
        frame=self._quote_frame(self._dhan_market_quote(mapping))
        values=self._normalize_live_quote(frame,security_id)
        if values is None:return None
        out={**values,"Datetime":datetime.now(INDIA_TZ),"price_source":"DHAN_OHLC"}
        with self._cache_lock:self._live_price_cache[key]=dict(out);self._live_price_cache_at[key]=time.monotonic()
        return out
    def get_latest_market_price(self,symbol):return self.get_latest_live_price(symbol,max_age_seconds=8)
    def get_index_1m(self,*args,**kwargs):return pd.DataFrame()
    def get_index_change_pct(self,ticker="NIFTY 500",intraday=None,max_age_seconds=10):
        q=dhan_data.index_quote(ticker)
        if not q:return None
        return float(q["NetChange"])/float(q["PreviousClose"])*100.0
    def today_only(self,df):return self._today(df)
    def latest_candle(self,symbol,interval="1m"):
        d=self.get_candles(symbol,interval,"1d");return None if d.empty else d.iloc[-1].to_dict()
