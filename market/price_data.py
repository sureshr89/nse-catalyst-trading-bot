"""Market price data for the NIFTY 500 price-action paper strategy."""

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
            return df
        data = df.copy()
        timestamps = pd.to_datetime(data["Datetime"], errors="coerce")
        try:
            if getattr(timestamps.dt, "tz", None) is None:
                timestamps = timestamps.dt.tz_localize(INDIA_TZ)
            else:
                timestamps = timestamps.dt.tz_convert(INDIA_TZ)
            current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
            return data[timestamps < current_minute].reset_index(drop=True)
        except Exception:
            return data

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
            if low in {"datetime", "date"}: rename[c] = "Datetime"
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
            if c in data.columns:
                data[c] = pd.to_numeric(data[c], errors="coerce")
        data = data.dropna(subset=required)
        keep = required + (["Volume"] if "Volume" in data.columns else [])
        return data[keep].sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    def get_candles(self, symbol, interval="5m", period="1d"):
        if interval not in self.valid_intervals:
            raise ValueError(f"Unsupported interval: {interval}")
        try:
            data = self._clean_data(yf.download(
                tickers=self.yahoo_symbol(symbol), period=period, interval=interval,
                auto_adjust=False, progress=False, threads=False, prepost=False,
                timeout=self.download_timeout,
            ))
            return self._completed_1m(data) if interval == "1m" else data
        except Exception as error:
            print(f"Price download failed for {symbol}: {error}")
            return pd.DataFrame()

    def get_1m(self, symbol):
        return self.get_candles(symbol, "1m", "1d")

    def get_latest_available_1m(self, symbol):
        """Return the latest completed 1-minute candle, never the live candle."""
        try:
            data = self._clean_data(yf.download(
                tickers=self.yahoo_symbol(symbol), period="1d", interval="1m",
                auto_adjust=False, progress=False, threads=False, prepost=False,
                timeout=self.download_timeout,
            ))
            data = self._completed_1m(self.today_only(data))
            return None if data.empty else data.iloc[-1].to_dict()
        except Exception as error:
            print(f"Latest available price failed for {symbol}: {error}")
            return None

    def get_5m(self, symbol):
        return self.get_candles(symbol, "5m", "1d")

    def get_daily(self, symbol, period="10d"):
        return self.get_candles(symbol, "1d", period)

    @staticmethod
    def _chunks(items, size):
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def _download_multi_batch(self, tickers, interval="1m", period="1d"):
        try:
            return yf.download(
                tickers=tickers, period=period, interval=interval,
                auto_adjust=False, progress=False, threads=False,
                prepost=False, group_by="ticker", timeout=self.download_timeout,
            )
        except Exception as error:
            print(f"Yahoo batch failed ({len(tickers)} tickers): {error}")
            return pd.DataFrame()

    def _extract_batch(self, batch, raw):
        result = {}
        tickers = [f"{s}.NS" for s in batch]
        if raw is None or raw.empty:
            return result
        if isinstance(raw.columns, pd.MultiIndex):
            level0 = set(raw.columns.get_level_values(0))
            level1 = set(raw.columns.get_level_values(1))
            for symbol, ticker in zip(batch, tickers):
                try:
                    if ticker in level0:
                        data = raw[ticker]
                    elif ticker in level1:
                        data = raw.xs(ticker, axis=1, level=1)
                    else:
                        data = pd.DataFrame()
                    cleaned = self._completed_1m(self._clean_data(data))
                    if not cleaned.empty:
                        result[symbol] = cleaned
                except Exception:
                    continue
        elif len(batch) == 1:
            cleaned = self._completed_1m(self._clean_data(raw))
            if not cleaned.empty:
                result[batch[0]] = cleaned
        return result

    def get_multi_1m(self, symbols):
        symbols = [str(s).upper().replace(".NS", "") for s in symbols]
        symbols = list(dict.fromkeys(s for s in symbols if s))
        if not symbols:
            return {}
        batches = list(self._chunks(symbols, self.batch_size))
        result = {}

        def download_with_retry(batch):
            tickers = [f"{s}.NS" for s in batch]
            raw = self._download_multi_batch(tickers, "1m", "1d")
            extracted = self._extract_batch(batch, raw)
            missing = [s for s in batch if s not in extracted]
            if missing:
                retry_raw = self._download_multi_batch([f"{s}.NS" for s in missing], "1m", "1d")
                extracted.update(self._extract_batch(missing, retry_raw))
            return extracted

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(download_with_retry, batch): batch for batch in batches}
            for future in as_completed(futures):
                try:
                    result.update(future.result())
                except Exception as error:
                    print("Yahoo batch worker failed:", error)

        for symbol in symbols:
            result.setdefault(symbol, pd.DataFrame())
        return result

    def get_index_1m(self, ticker="^NSEI"):
        try:
            data = self._clean_data(yf.download(
                tickers=ticker, period="1d", interval="1m", auto_adjust=False,
                progress=False, threads=False, prepost=False, timeout=self.download_timeout,
            ))
            return self._completed_1m(data)
        except Exception as error:
            print("NIFTY market-index data failed:", error)
            return pd.DataFrame()

    def today_only(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        result = df.copy()
        result["Datetime"] = self._to_ist(result["Datetime"])
        result = result.dropna(subset=["Datetime"])
        if result.empty:
            return pd.DataFrame()
        latest_date = result["Datetime"].dt.date.max()
        return result[result["Datetime"].dt.date == latest_date].sort_values("Datetime").reset_index(drop=True)

    def latest_candle(self, symbol, interval="1m"):
        df = self.today_only(self.get_candles(symbol, interval, "1d"))
        return None if df.empty else df.iloc[-1].to_dict()
