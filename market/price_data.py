"""Live 1-minute market price data for the NIFTY 500 paper strategy."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

INDIA_TZ = ZoneInfo("Asia/Kolkata")

class PriceData:
    def __init__(self):
        self.valid_intervals={"1m","5m","1d"}; self.download_timeout=10; self.batch_size=25; self.max_workers=4; self.batch_retries=1
    def yahoo_symbol(self,symbol):
        symbol=str(symbol).strip().upper()
        if symbol.startswith("^"): return symbol
        return symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    @staticmethod
    def _to_ist(series):
        values=pd.to_datetime(series,errors="coerce")
        try:return values.dt.tz_localize(INDIA_TZ) if getattr(values.dt,"tz",None) is None else values.dt.tz_convert(INDIA_TZ)
        except Exception:return values
    @staticmethod
    def _completed_1m(df):
        if df is None or df.empty or "Datetime" not in df.columns:return pd.DataFrame()
        data=df.copy(); timestamps=pd.to_datetime(data["Datetime"],errors="coerce")
        try:
            timestamps=timestamps.dt.tz_localize(INDIA_TZ) if getattr(timestamps.dt,"tz",None) is None else timestamps.dt.tz_convert(INDIA_TZ)
            valid=timestamps.notna() & (timestamps < datetime.now(INDIA_TZ).replace(second=0,microsecond=0)); return data.loc[valid].copy().reset_index(drop=True)
        except Exception:return pd.DataFrame()
    def _clean_data(self,df):
        if df is None or df.empty:return pd.DataFrame()
        data=df.copy()
        if isinstance(data.columns,pd.MultiIndex):data.columns=[c[0] if isinstance(c,tuple) else c for c in data.columns]
        data=data.reset_index(); rename={}
        for c in data.columns:
            low=str(c).strip().lower()
            if low in {"datetime","date"}:rename[c]="Datetime"
            elif low=="open":rename[c]="Open"
            elif low=="high":rename[c]="High"
            elif low=="low":rename[c]="Low"
            elif low=="close":rename[c]="Close"
            elif low=="volume":rename[c]="Volume"
        data=data.rename(columns=rename); required=["Datetime","Open","High","Low","Close"]
        if any(c not in data.columns for c in required):return pd.DataFrame()
        data["Datetime"]=self._to_ist(data["Datetime"])
        for c in ["Open","High","Low","Close","Volume"]:
            if c in data.columns:data[c]=pd.to_numeric(data[c],errors="coerce")
        data=data.dropna(subset=required); keep=required+(["Volume"] if "Volume" in data.columns else [])
        return data[keep].sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)
    def get_candles(self,symbol,interval="5m",period="1d"):
        if interval not in self.valid_intervals:raise ValueError(f"Unsupported interval: {interval}")
        try:
            data=self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol),period=period,interval=interval,auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout)); return self._completed_1m(data) if interval=="1m" else data
        except Exception as error:print(f"Price download failed for {symbol}: {error}");return pd.DataFrame()
    def get_1m(self,symbol):return self.get_candles(symbol,"1m","1d")
    def _today_intraday(self,data):
        if data is None or data.empty or "Datetime" not in data.columns:return pd.DataFrame()
        result=data.copy();result["Datetime"]=self._to_ist(result["Datetime"]);result=result.dropna(subset=["Datetime"])
        if result.empty:return pd.DataFrame()
        return result[result["Datetime"].dt.date==datetime.now(INDIA_TZ).date()].sort_values("Datetime").reset_index(drop=True)
    def get_latest_available_1m(self,symbol):
        try:
            data=self._completed_1m(self._today_intraday(self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol),period="1d",interval="1m",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout))));return None if data.empty else data.iloc[-1].to_dict()
        except Exception:return None
    def get_latest_market_price(self,symbol):
        try:
            today=self._completed_1m(self._today_intraday(self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol),period="1d",interval="1m",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout))))
            if not today.empty:
                latest=today.iloc[-1];ts=pd.Timestamp(latest["Datetime"]);ts=ts.tz_localize(INDIA_TZ) if ts.tzinfo is None else ts.tz_convert(INDIA_TZ)
                if 0 <= (datetime.now(INDIA_TZ)-ts.to_pydatetime()).total_seconds() <= 120:return {"Close":float(latest["Close"]),"Datetime":ts.to_pydatetime(),"price_source":"recent_1m"}
        except Exception:pass
        return None
    def get_5m(self,symbol):return self.get_candles(symbol,"5m","1d")
    def get_daily(self,symbol,period="10d"):return self.get_candles(symbol,"1d",period)
    @staticmethod
    def _chunks(items,size):
        for i in range(0,len(items),size):yield items[i:i+size]
    def _download_multi_batch(self,tickers,interval="1m",period="1d"):
        try:return yf.download(tickers=tickers,period=period,interval=interval,auto_adjust=False,progress=False,threads=False,prepost=False,group_by="ticker",timeout=self.download_timeout)
        except Exception as error:print(f"Yahoo batch failed ({len(tickers)}):",error);return pd.DataFrame()
    def _extract_batch(self,batch,raw,completed=True,today_only=True):
        result={};tickers=[f"{s}.NS" for s in batch]
        if raw is None or raw.empty:return result
        if isinstance(raw.columns,pd.MultiIndex):
            level0=set(raw.columns.get_level_values(0));level1=set(raw.columns.get_level_values(1))
            for symbol,ticker in zip(batch,tickers):
                try:
                    if ticker in level0:data=raw[ticker]
                    elif ticker in level1:data=raw.xs(ticker,axis=1,level=1)
                    else:continue
                    cleaned=self._clean_data(data);cleaned=self._completed_1m(cleaned) if completed else cleaned
                    if today_only:cleaned=self._today_intraday(cleaned)
                    if not cleaned.empty:result[symbol]=cleaned
                except Exception:continue
        elif len(batch)==1:
            cleaned=self._clean_data(raw);cleaned=self._completed_1m(cleaned) if completed else cleaned
            if today_only:cleaned=self._today_intraday(cleaned)
            if not cleaned.empty:result[batch[0]]=cleaned
        return result
    def get_multi_daily(self,symbols,period="5d"):
        """Batch daily OHLC. Gap detection must not depend on 1-minute feed availability."""
        symbols=list(dict.fromkeys(str(s).upper().replace(".NS","") for s in symbols if str(s).strip()));result={}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures={executor.submit(self._download_multi_batch,[f"{s}.NS" for s in b],"1d",period):b for b in self._chunks(symbols,self.batch_size)}
            for future in as_completed(futures):
                try:result.update(self._extract_batch(futures[future],future.result(),completed=False,today_only=False))
                except Exception as error:print("Daily batch failed:",error)
        for s in symbols:result.setdefault(s,pd.DataFrame())
        return result
    def get_multi_1m(self,symbols):
        symbols=list(dict.fromkeys(str(s).upper().replace(".NS","") for s in symbols if str(s).strip()));result={}
        def worker(batch):
            raw=self._download_multi_batch([f"{s}.NS" for s in batch],"1m","1d");out=self._extract_batch(batch,raw,True,True);missing=[s for s in batch if s not in out]
            if missing:out.update(self._extract_batch(missing,self._download_multi_batch([f"{s}.NS" for s in missing],"1m","1d"),True,True))
            return out
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures={executor.submit(worker,b):b for b in self._chunks(symbols,self.batch_size)}
            for future in as_completed(futures):
                try:result.update(future.result())
                except Exception:pass
        for s in symbols:result.setdefault(s,pd.DataFrame())
        return result
    def get_index_1m(self,ticker="^CRSLDX"):
        try:return self._completed_1m(self._today_intraday(self._clean_data(yf.download(tickers=ticker,period="1d",interval="1m",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout))))
        except Exception:return pd.DataFrame()
    def get_index_change_pct(self,ticker="^CRSLDX"):
        try:
            data=self._clean_data(yf.download(tickers=ticker,period="5d",interval="1d",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout));prior=data[data["Datetime"].dt.date<datetime.now(INDIA_TZ).date()];intraday=self.get_index_1m(ticker)
            if prior.empty or intraday.empty:return None
            return (float(intraday.iloc[-1]["Close"])/float(prior.iloc[-1]["Close"])-1)*100
        except Exception:return None
    def today_only(self,df):return self._today_intraday(df)
    def latest_candle(self,symbol,interval="1m"):
        df=self.today_only(self.get_candles(symbol,interval,"1d"));return None if df.empty else df.iloc[-1].to_dict()
