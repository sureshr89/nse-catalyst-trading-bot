"""Dhan-only price data for the clean S1-S5 paper-trading pipeline."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading
import time
import pandas as pd
import market.dhan_data as dhan_data

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class PriceData:
    _cache_lock = threading.RLock()
    _live_price_cache = {}
    _live_price_cache_at = {}

    def __init__(self):
        self.valid_intervals = {"1m", "5m", "1d"}

    @staticmethod
    def _clean(df):
        if df is None or df.empty or "Datetime" not in df.columns:
            return pd.DataFrame()
        x = df.copy()
        x["Datetime"] = pd.to_datetime(x["Datetime"], errors="coerce")
        try:
            x["Datetime"] = x["Datetime"].dt.tz_convert(INDIA_TZ) if x["Datetime"].dt.tz is not None else x["Datetime"].dt.tz_localize(INDIA_TZ)
        except Exception:
            return pd.DataFrame()
        required = ["Datetime", "Open", "High", "Low", "Close"]
        if any(c not in x.columns for c in required):
            return pd.DataFrame()
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in x.columns:
                x[c] = pd.to_numeric(x[c], errors="coerce")
        x = x.dropna(subset=required)
        x = x[(x["Open"] > 0) & (x["High"] >= x[["Open", "Low", "Close"]].max(axis=1)) & (x["Low"] <= x[["Open", "High", "Close"]].min(axis=1))]
        return x.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    @classmethod
    def _completed(cls, df):
        x = cls._clean(df)
        if x.empty:
            return x
        cutoff = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        return x[x["Datetime"] < cutoff].reset_index(drop=True)

    def _map(self, symbols):
        return dhan_data.map_nifty500(symbols)

    def get_candles(self, symbol, interval="5m", period="1d"):
        if interval not in self.valid_intervals:
            raise ValueError(f"Unsupported interval: {interval}")
        if not dhan_data.configured():
            return pd.DataFrame()
        mapping = self._map([symbol])
        if mapping is None or len(mapping) != 1:
            return pd.DataFrame()
        sid = str(mapping.iloc[0]["SecurityId"])
        now = datetime.now(INDIA_TZ)
        today = now.date()
        if interval == "1d":
            raw = str(period).strip().lower()
            days = int(raw[:-1]) if raw.endswith("d") and raw[:-1].isdigit() else 10
            days = max(1, days)
            return self._clean(dhan_data.daily_history(sid, (today - timedelta(days=days + 5)).isoformat(), (today + timedelta(days=1)).isoformat()))
        minutes = {"1m": 1, "5m": 5}[interval]
        frame = dhan_data.intraday_history(sid, f"{today.isoformat()} 09:00:00", now.strftime("%Y-%m-%d %H:%M:%S"), minutes)
        return self._completed(frame)

    def get_1m(self, symbol):
        return self.get_candles(symbol, "1m", "1d")

    def get_5m(self, symbol):
        return self.get_candles(symbol, "5m", "1d")

    def get_daily(self, symbol, period="10d"):
        return self.get_candles(symbol, "1d", period)

    def get_multi_daily(self, symbols, period="10d"):
        symbols = list(dict.fromkeys(str(s).upper().replace(".NS", "").strip() for s in symbols if str(s).strip()))
        if not symbols or not dhan_data.configured():
            return {}
        mapping = self._map(symbols)
        if mapping is None or mapping.empty:
            return {}
        by_symbol = {str(r["Symbol"]).upper(): str(r["SecurityId"]) for _, r in mapping.iterrows()}
        now = datetime.now(INDIA_TZ)
        today = now.date()
        raw = str(period).strip().lower()
        days = int(raw[:-1]) if raw.endswith("d") and raw[:-1].isdigit() else 10
        start = (today - timedelta(days=max(1, days) + 5)).isoformat()
        end = (today + timedelta(days=1)).isoformat()
        result = {}
        for symbol in symbols:
            sid = by_symbol.get(symbol)
            if not sid:
                continue
            try:
                frame = dhan_data.daily_history(sid, start, end)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    result[symbol] = frame
            except Exception:
                continue
            time.sleep(0.21)
        return result

    @staticmethod
    def _quote_row(quote, symbol, security_id=None):
        if quote is None:
            return None
        if isinstance(quote, pd.Series):
            quote = quote.to_frame().T
        if not isinstance(quote, pd.DataFrame) or quote.empty:
            return None
        required = {"LTP", "TodayOpen", "TodayHigh", "TodayLow", "PreviousClose"}
        if not required.issubset(quote.columns):
            return None
        clean = quote.copy()
        wanted = str(symbol).upper().replace(".NS", "").strip()
        if "Symbol" in clean.columns:
            normalized = clean["Symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False).str.strip()
            matched = clean[normalized.eq(wanted)]
            if not matched.empty:
                return matched.iloc[0]
        if security_id is not None and "SecurityId" in clean.columns:
            matched = clean[clean["SecurityId"].astype(str).eq(str(security_id))]
            if not matched.empty:
                return matched.iloc[0]
        return clean.iloc[0]

    def get_latest_live_price(self, symbol, max_age_seconds=8):
        key = str(symbol).upper().replace(".NS", "").strip()
        if not key or not dhan_data.configured():
            return None
        now = time.monotonic()
        if max_age_seconds > 0:
            with self._cache_lock:
                cached = self._live_price_cache.get(key)
                if cached is not None and now - self._live_price_cache_at.get(key, 0) <= max_age_seconds:
                    return dict(cached)
        mapping = self._map([key])
        if mapping is None or len(mapping) != 1:
            return None
        security_id = str(mapping.iloc[0]["SecurityId"])
        try:
            # Keep the PriceData -> Dhan boundary on the canonical public API.
            # The adapter owns its own short-lived market-feed cache.
            quote = dhan_data.market_quote(mapping)
            row = self._quote_row(quote, key, security_id)
            if row is None:
                return None
            close = float(row["LTP"])
            open_price = float(row["TodayOpen"])
            high = float(row["TodayHigh"])
            low = float(row["TodayLow"])
            previous_close = float(row["PreviousClose"])
            net_change = float(row["NetChange"]) if "NetChange" in row.index else close - previous_close
            values = [close, open_price, high, low, previous_close]
            if any(pd.isna(v) or v <= 0 for v in values):
                return None
            if high < max(open_price, low, close) or low > min(open_price, high, close):
                return None
            out = {"Close": close, "Open": open_price, "High": high, "Low": low, "PreviousClose": previous_close, "NetChange": net_change, "Datetime": datetime.now(INDIA_TZ), "price_source": "DHAN_MARKETFEED_QUOTE"}
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        with self._cache_lock:
            self._live_price_cache[key] = dict(out)
            self._live_price_cache_at[key] = time.monotonic()
        return out

    def get_latest_market_price(self, symbol):
        return self.get_latest_live_price(symbol, max_age_seconds=2)

    def get_index_1m(self, *args, **kwargs):
        return pd.DataFrame()

    def get_index_change_pct(self, ticker="NIFTY 500", intraday=None, max_age_seconds=10):
        quote = dhan_data.index_quote(ticker)
        if not quote:
            return None
        try:
            return float(quote["NetChange"]) / float(quote["PreviousClose"]) * 100.0
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None

    def today_only(self, df):
        x = self._clean(df)
        return x[x["Datetime"].dt.date == datetime.now(INDIA_TZ).date()].reset_index(drop=True) if not x.empty else x

    def latest_candle(self, symbol, interval="1m"):
        d = self.get_candles(symbol, interval, "1d")
        return None if d.empty else d.iloc[-1].to_dict()
