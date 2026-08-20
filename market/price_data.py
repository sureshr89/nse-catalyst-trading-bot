"""Dhan-only price data for the clean S1-S5 paper-trading pipeline."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading, time
import pandas as pd

INDIA_TZ=ZoneInfo("Asia/Kolkata")

class PriceData:
    _cache_lock=threading.RLock(); _multi_1m_cache={}; _multi_1m_cache_at={}; _multi_daily_cache={}; _multi_daily_cache_at={}; _live_price_cache={}; _live_price_cache_at={}
    def __init__(self): self.valid_intervals={"1m","5m","1d"}; self.max_workers=4
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
        cutoff=datetime.now(INDIA_TZ).replace(second=0,microsecond=0)
        return x[x["Datetime"]<cutoff].copy().reset_index(drop=True)
    def _today(self,df):
        x=self._clean(df);return x[x["Datetime"].dt.date==datetime.now(INDIA_TZ).date()].reset_index(drop=True) if not x.empty else x
    def _map(self,symbols):
        from market.dhan_data import map_nifty500
        return map_nifty500(symbols)
    def get_candles(self,symbol,interval="5m",period="1d"):
        if interval not in self.valid_intervals:raise ValueError(f"Unsupported interval: {interval}")
        from market.dhan_data import configured,intraday_history,daily_history
        if not configured():return pd.DataFrame()
        m=self._map([symbol])
        if len(m)!=1:return pd.DataFrame()
        sid=str(m.iloc[0]["SecurityId"]);now=datetime.now(INDIA_TZ);today=now.date()
        if interval=="1d":
            raw=str(period).strip().lower();days=int(raw[:-1]) if raw.endswith("d") and raw[:-1].isdigit() else 10;days=max(1,days)
            return daily_history(sid,(today-timedelta(days=days+5)).isoformat(),(today+timedelta(days=1)).isoformat())
        return self._completed(intraday_history(sid,f"{today.isoformat()} 09:00:00",now.strftime("%Y-%m-%d %H:%M:%S"),{"1m":1,"5m":5}[interval]))
    def get_1m(self,symbol):return self.get_candles(symbol,"1m","1d")
    def get_5m(self,symbol):return self.get_candles(symbol,"5m","1d")
    def get_daily(self,symbol,period="10d"):return self.get_candles(symbol,"1d",period)
    def get_multi_daily(self,symbols,period="10d"):
        symbols=tuple(dict.fromkeys(str(s).upper().replace(".NS","") for s in symbols if str(s).strip()));now=time.monotonic()
        with self._cache_lock:
            cached=self._multi_daily_cache.get((symbols,period))
            if cached is not None and now-self._multi_daily_cache_at.get((symbols,period),0)<300:return {k:v.copy() for k,v in cached.items()}
        mapping=self._map(symbols);result={s:pd.DataFrame() for s in symbols};from market.dhan_data import daily_history
        raw=str(period).strip().lower();days=int(raw[:-1]) if raw.endswith("d") and raw[:-1].isdigit() else 10;days=max(1,days)
        def one(row):
            try:return str(row["Symbol"]).upper(),daily_history(str(row["SecurityId"]),(datetime.now(INDIA_TZ).date()-timedelta(days=days+5)).isoformat(),(datetime.now(INDIA_TZ).date()+timedelta(days=1)).isoformat())
            except Exception:return str(row["Symbol"]).upper(),pd.DataFrame()
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for f in as_completed([pool.submit(one,row) for _,row in mapping.iterrows()]):
                try:s,d=f.result();result[s]=d
                except Exception:pass
        with self._cache_lock:self._multi_daily_cache[(symbols,period)]=result;self._multi_daily_cache_at[(symbols,period)]=time.monotonic()
        return {k:v.copy() for k,v in result.items()}
    def get_multi_1m(self,symbols):
        symbols=tuple(dict.fromkeys(str(s).upper().replace(".NS","") for s in symbols if str(s).strip()));now=time.monotonic()
        with self._cache_lock:
            cached=self._multi_1m_cache.get(symbols)
            if cached is not None and now-self._multi_1m_cache_at.get(symbols,0)<45:return {k:v.copy() for k,v in cached.items()}
        mapping=self._map(symbols);result={s:pd.DataFrame() for s in symbols};today=datetime.now(INDIA_TZ).date();start=f"{today.isoformat()} 09:00:00";end=datetime.now(INDIA_TZ).strftime("%Y-%m-%d %H:%M:%S");from market.dhan_data import intraday_history
        def one(row):
            try:return str(row["Symbol"]).upper(),self._completed(intraday_history(str(row["SecurityId"]),start,end,1))
            except Exception:return str(row["Symbol"]).upper(),pd.DataFrame()
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for f in as_completed([pool.submit(one,row) for _,row in mapping.iterrows()]):
                try:s,d=f.result();result[s]=d
                except Exception:pass
        with self._cache_lock:self._multi_1m_cache[symbols]=result;self._multi_1m_cache_at[symbols]=time.monotonic()
        return {k:v.copy() for k,v in result.items()}
    def get_latest_live_price(self,symbol,max_age_seconds=8):
        key=str(symbol).upper().replace(".NS","");now=time.monotonic()
        with self._cache_lock:
            cached=self._live_price_cache.get(key)
            if cached is not None and now-self._live_price_cache_at.get(key,0)<=max_age_seconds:return dict(cached)
        from market.dhan_data import map_nifty500,market_quote
        m=map_nifty500([key]);q=market_quote(m,cache_seconds=1) if len(m)==1 else pd.DataFrame()
        if q.empty:return None
        r=q.iloc[0];out={"Close":float(r["LTP"]),"Datetime":datetime.now(INDIA_TZ),"Open":float(r["TodayOpen"]),"High":float(r["TodayHigh"]),"Low":float(r["TodayLow"]),"PreviousClose":float(r["PreviousClose"]),"NetChange":float(r["NetChange"]),"price_source":"Dhan"}
        with self._cache_lock:self._live_price_cache[key]=dict(out);self._live_price_cache_at[key]=time.monotonic()
        return out
    def get_latest_market_price(self,symbol):return self.get_latest_live_price(symbol,max_age_seconds=8)
    def get_index_1m(self,*args,**kwargs):return pd.DataFrame()
    def get_index_change_pct(self,ticker="NIFTY 500",intraday=None,max_age_seconds=10):
        from market.dhan_data import index_quote
        q=index_quote(ticker)
        if not q:return None
        return float(q["NetChange"])/float(q["PreviousClose"])*100.0
    def today_only(self,df):return self._today(df)
    def latest_candle(self,symbol,interval="1m"):
        d=self.get_candles(symbol,interval,"1d");return None if d.empty else d.iloc[-1].to_dict()
