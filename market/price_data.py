"""Price data engine for the pure price-action paper strategy."""
import pandas as pd
import yfinance as yf


class PriceData:
    def __init__(self):
        self.valid_intervals = {"1m", "5m", "1d"}
        self.download_timeout = 10

    def yahoo_symbol(self, symbol):
        symbol = str(symbol).strip().upper()
        return symbol if symbol.endswith(".NS") else f"{symbol}.NS"

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
        data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
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
            return self._clean_data(yf.download(
                tickers=self.yahoo_symbol(symbol), period=period, interval=interval,
                auto_adjust=False, progress=False, threads=False, prepost=False,
                timeout=self.download_timeout,
            ))
        except Exception as error:
            print(f"Price download failed for {symbol}: {error}")
            return pd.DataFrame()

    def get_1m(self, symbol):
        return self.get_candles(symbol, "1m", "1d")

    def get_5m(self, symbol):
        return self.get_candles(symbol, "5m", "1d")

    def get_daily(self, symbol, period="10d"):
        return self.get_candles(symbol, "1d", period)

    def get_multi_1m(self, symbols):
        """Batch 1-minute download for the Nifty 100 scanner."""
        symbols = [str(s).upper().replace(".NS", "") for s in symbols]
        tickers = [f"{s}.NS" for s in symbols]
        if not tickers:
            return {}
        try:
            raw = yf.download(
                tickers=tickers, period="1d", interval="1m", auto_adjust=False,
                progress=False, threads=True, prepost=False, group_by="ticker",
                timeout=self.download_timeout,
            )
        except Exception as error:
            print("Batch 1-minute download failed:", error)
            return {}
        result = {}
        if isinstance(raw.columns, pd.MultiIndex):
            level0 = set(raw.columns.get_level_values(0))
            level1 = set(raw.columns.get_level_values(1))
            for symbol, ticker in zip(symbols, tickers):
                try:
                    if ticker in level0:
                        result[symbol] = self._clean_data(raw[ticker])
                    elif ticker in level1:
                        result[symbol] = self._clean_data(raw.xs(ticker, axis=1, level=1))
                except Exception:
                    result[symbol] = pd.DataFrame()
        else:
            result[symbols[0]] = self._clean_data(raw)
        return result

    def get_index_1m(self, ticker="^CNX100"):
        try:
            return self._clean_data(yf.download(
                tickers=ticker, period="1d", interval="1m", auto_adjust=False,
                progress=False, threads=False, prepost=False, timeout=self.download_timeout,
            ))
        except Exception as error:
            print("Nifty 100 data failed:", error)
            return pd.DataFrame()

    def today_only(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        result = df.copy()
        result["Datetime"] = pd.to_datetime(result["Datetime"], errors="coerce")
        result = result.dropna(subset=["Datetime"])
        if result.empty:
            return pd.DataFrame()
        latest_date = result["Datetime"].dt.date.max()
        return result[result["Datetime"].dt.date == latest_date].sort_values("Datetime").reset_index(drop=True)

    def latest_candle(self, symbol, interval="1m"):
        df = self.today_only(self.get_candles(symbol, interval, "1d"))
        return None if df.empty else df.iloc[-1].to_dict()
