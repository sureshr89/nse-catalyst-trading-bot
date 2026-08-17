"""Live 1-minute market price data for the NIFTY 500 paper strategy."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class PriceData:
    def __init__(self):
        self.valid_intervals = {"1m", "5m", "1d"}
        self.download_timeout = 10
        self.batch_size = 25
        self.max_workers = 4
        self.batch_retries = 1

    def yahoo_symbol(self, symbol):
        symbol = str(symbol).strip().upper()
        if symbol.startswith("^"):
            return symbol
        return symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    @staticmethod
    def _to_ist(series):
        values = pd.to_datetime(series, errors="coerce")
        try:
            if getattr(values.dt, "tz", None) is None:
                return values.dt.tz_localize(INDIA_TZ)
            return values.dt.tz_convert(INDIA_TZ)
        except Exception:
            return values

    @staticmethod
    def _completed_1m(df):
        if df is None or df.empty or "Datetime" not in df.columns:
            return pd.DataFrame()
        data = df.copy()
        timestamps = pd.to_datetime(data["Datetime"], errors="coerce")
        try:
            if getattr(timestamps.dt, "tz", None) is None:
                timestamps = timestamps.dt.tz_localize(INDIA_TZ)
            else:
                timestamps = timestamps.dt.tz_convert(INDIA_TZ)
            valid = timestamps.notna()
            current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
            valid &= timestamps < current_minute
            return data.loc[valid].copy().reset_index(drop=True)
        except Exception as error:
            print(f"1-minute completion validation failed: {type(error).__name__}: {error}")
            return pd.DataFrame()

    def _clean_data(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        data = df.copy()
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
        data = data.reset_index()
        rename = {}
        for c in data.columns:
            low = str(c).strip().lower()
            if low in {"datetime", "date"}:
                rename[c] = "Datetime"
            elif low == "open": rename[c] = "Open"
            elif low == "high": rename[c] = "High"
            elif low == "low": rename[c] = "Low"
            elif low == "close": rename[c] = "Close"
            elif low == "volume": rename[c] = "Volume"
        data = data.rename(columns=rename)
        required = ["Datetime", "Open", "High", "Low", "Close"]
        if any(c not in data.columns for c in required):
            return pd.DataFrame()
        data["Datetime"] = self._to_ist(data["Datetime"])
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in data.columns: data[c] = pd.to_numeric(data[c], errors="coerce")
        data = data.dropna(subset=required)
        keep = required + (["Volume"] if "Volume" in data.columns else [])
        return data[keep].sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    def get_candles(self, symbol, interval="5m", period="1d"):
        if interval not in self.valid_intervals:
            raise ValueError(f"Unsupported interval: {interval}")
        try:
            data = self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol), period=period, interval=interval, auto_adjust=False, progress=False, threads=False, prepost=False, timeout=self.download_timeout))
            return self._completed_1m(data) if interval == "1m" else data
        except Exception as error:
            print(f"Price download failed for {symbol}: {error}")
            return pd.DataFrame()

    def get_1m(self, symbol): return self.get_candles(symbol, "1m", "1d")

    def _today_intraday(self, data):
        if data is None or data.empty or "Datetime" not in data.columns: return pd.DataFrame()
        result = data.copy(); result["Datetime"] = self._to_ist(result["Datetime"]); result = result.dropna(subset=["Datetime"])
        if result.empty: return pd.DataFrame()
        today = datetime.now(INDIA_TZ).date()
        return result[result["Datetime"].dt.date == today].sort_values("Datetime").reset_index(drop=True)

    def get_latest_available_1m(self, symbol):
        try:
            data = self._completed_1m(self._today_intraday(self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol), period="1d", interval="1m", auto_adjust=False, progress=False, threads=False, prepost=False, timeout=self.download_timeout))))
            return None if data.empty else data.iloc[-1].to_dict()
        except Exception as error:
            print(f"Latest completed price failed for {symbol}: {error}")
            return None

    def get_latest_market_price(self, symbol):
        now = datetime.now(INDIA_TZ)
        try:
            raw = self._clean_data(yf.download(tickers=self.yahoo_symbol(symbol), period="1d", interval="1m", auto_adjust=False, progress=False, threads=False, prepost=False, timeout=self.download_timeout))
            today = self._completed_1m(self._today_intraday(raw))
            if not today.empty:
                latest = today.iloc[-1]; candle_time = pd.Timestamp(latest["Datetime"])
                candle_time = candle_time.tz_localize(INDIA_TZ) if candle_time.tzinfo is None else candle_time.tz_convert(INDIA_TZ)
                age_seconds = (now - candle_time.to_pydatetime()).total_seconds()
                if 0 <= age_seconds <= 120:
                    return {"Close": float(latest["Close"]), "Datetime": candle_time.to_pydatetime(), "price_source": "recent_1m"}
                print(f"Current quote for {symbol} is stale ({age_seconds:.0f}s)")
        except Exception as error:
            print(f"Intraday market price failed for {symbol}: {type(error).__name__}: {error}")
        return None

    def get_5m(self, symbol): return self.get_candles(symbol, "5m", "1d")
    def get_daily(self, symbol, period="10d"): return self.get_candles(symbol, "1d", period)

    @staticmethod
    def _chunks(items, size):
        for i in range(0, len(items), size): yield items[i:i + size]

    def _download_multi_batch(self, tickers, interval="1m", period="1d"):
        try:
            return yf.download(tickers=tickers, period=period, interval=interval, auto_adjust=False, progress=False, threads=False, prepost=False, group_by="ticker", timeout=self.download_timeout)
        except Exception as error:
            print(f"Yahoo batch failed ({len(tickers)} tickers): {error}")
            return pd.DataFrame()

    def _extract_batch(self, batch, raw):
        result = {}
        tickers = [f"{s}.NS" for s in batch]
        if raw is None or raw.empty: return result
        if isinstance(raw.columns, pd.MultiIndex):
            level0=set(raw.columns.get_level_values(0)); level1=set(raw.columns.get_level_values(1))
            for symbol,ticker in zip(batch,tickers):
                try:
                    if ticker in level0: data=raw[ticker]
                    elif ticker in level1: data=raw.xs(ticker,axis=1,level=1)
                    else: continue
                    cleaned=self._completed_1m(self._today_intraday(self._clean_data(data)))
                    if not cleaned.empty: result[symbol]=cleaned
                except Exception: continue
        elif len(batch)==1:
            cleaned=self._completed_1m(self._today_intraday(self._clean_data(raw)))
            if not cleaned.empty: result[batch[0]]=cleaned
        return result

    def get_multi_1m(self, symbols):
        symbols=[str(s).upper().replace(".NS","") for s in symbols]; symbols=list(dict.fromkeys(s for s in symbols if s))
        if not symbols: return {}
        batches=list(self._chunks(symbols,self.batch_size)); result={}
        def download_with_retry(batch):
            raw=self._download_multi_batch([f"{s}.NS" for s in batch],"1m","1d")
            extracted=self._extract_batch(batch,raw); missing=[s for s in batch if s not in extracted]
            if missing:
                retry_raw=self._download_multi_batch([f"{s}.NS" for s in missing],"1m","1d")
                extracted.update(self._extract_batch(missing,retry_raw))
            return extracted
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures={executor.submit(download_with_retry,b):b for b in batches}
            for future in as_completed(futures):
                try: result.update(future.result())
                except Exception as error: print("Yahoo batch worker failed:",error)
        for symbol in symbols: result.setdefault(symbol,pd.DataFrame())

        # IMPORTANT: do not reject the entire NIFTY 500 because one or a few stocks
        # have an older last tick. That old global common-snapshot check was turning
        # the whole scanner into zero data. Each stock is already restricted to
        # completed 1m candles; keep the usable symbols and let scanner coverage
        # decide whether enough symbols are available.
        now=datetime.now(INDIA_TZ)
        stale=[]
        for symbol,df in list(result.items()):
            if df is None or df.empty: continue
            ts=self._to_ist(df["Datetime"]); latest=ts.max()
            age=(now-latest.to_pydatetime()).total_seconds()
            if age < 0 or age > 180:
                stale.append((symbol,round(age)))
                result[symbol]=pd.DataFrame()
        if stale: print(f"Excluded {len(stale)} stale stock streams; retained usable NIFTY 500 streams")
        return result

    def get_index_1m(self,ticker="^CRSLDX"):
        try:
            data=self._clean_data(yf.download(tickers=ticker,period="1d",interval="1m",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout))
            return self._completed_1m(self._today_intraday(data))
        except Exception as error:
            print("NIFTY 500 index data failed:",error); return pd.DataFrame()

    def get_index_change_pct(self,ticker="^CRSLDX"):
        try:
            data=self._clean_data(yf.download(tickers=ticker,period="5d",interval="1d",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=self.download_timeout))
            if data.empty:return None
            data=data.sort_values("Datetime").dropna(subset=["Close"]); today=datetime.now(INDIA_TZ).date(); prior=data[data["Datetime"].dt.date<today]
            if prior.empty:return None
            previous_close=float(prior.iloc[-1]["Close"]); intraday=self.get_index_1m(ticker)
            if intraday.empty or previous_close<=0:return None
            current_price=float(intraday.iloc[-1]["Close"]); return (current_price/previous_close-1.0)*100.0
        except Exception as error:
            print(f"NIFTY 500 change calculation failed: {type(error).__name__}: {error}"); return None

    def today_only(self,df):
        if df is None or df.empty or "Datetime" not in df.columns:return pd.DataFrame()
        result=df.copy(); result["Datetime"]=self._to_ist(result["Datetime"]); result=result.dropna(subset=["Datetime"])
        if result.empty:return pd.DataFrame()
        today=datetime.now(INDIA_TZ).date(); return result[result["Datetime"].dt.date==today].sort_values("Datetime").reset_index(drop=True)

    def latest_candle(self,symbol,interval="1m"):
        df=self.today_only(self.get_candles(symbol,interval,"1d")); return None if df.empty else df.iloc[-1].to_dict()
