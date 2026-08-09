"""
PRICE DATA ENGINE
=================

Free market-data source: yfinance

5-minute candles = setup / pullback
1-minute candles = final breakout confirmation
"""

from datetime import datetime

import pandas as pd
import yfinance as yf


class PriceData:

    def __init__(self):
        self.valid_intervals = {"1m", "5m"}

    def yahoo_symbol(self, symbol):
        symbol = str(symbol).strip().upper()
        if symbol.endswith(".NS"):
            return symbol
        return f"{symbol}.NS"

    def _clean_data(self, df):
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                column[0] if isinstance(column, tuple) else column
                for column in df.columns
            ]

        rename_map = {}
        for column in df.columns:
            name = str(column).strip()
            lower = name.lower()
            if lower == "open": rename_map[column] = "Open"
            elif lower == "high": rename_map[column] = "High"
            elif lower == "low": rename_map[column] = "Low"
            elif lower == "close": rename_map[column] = "Close"
            elif lower == "volume": rename_map[column] = "Volume"

        df = df.rename(columns=rename_map)

        for column in ["Open", "High", "Low", "Close"]:
            if column not in df.columns:
                return pd.DataFrame()

        df = df.reset_index()

        datetime_column = None
        for column in df.columns:
            if str(column).lower() in {"datetime", "date"}:
                datetime_column = column
                break

        if datetime_column is None:
            return pd.DataFrame()

        df = df.rename(columns={datetime_column: "Datetime"})
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
        df = df.dropna(subset=["Datetime"])

        try:
            if df["Datetime"].dt.tz is not None:
                df["Datetime"] = df["Datetime"].dt.tz_convert("Asia/Kolkata")
        except Exception:
            pass

        for column in ["Open", "High", "Low", "Close", "Volume"]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=["Open", "High", "Low", "Close"])

        keep_columns = ["Datetime", "Open", "High", "Low", "Close"]
        if "Volume" in df.columns:
            keep_columns.append("Volume")

        return (
            df[keep_columns]
            .sort_values("Datetime")
            .drop_duplicates(subset=["Datetime"])
            .reset_index(drop=True)
        )

    def get_candles(self, symbol, interval="5m", period="1d"):
        if interval not in self.valid_intervals:
            raise ValueError(f"Unsupported interval: {interval}")

        ticker = self.yahoo_symbol(symbol)

        try:
            df = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                prepost=False,
            )
            return self._clean_data(df)
        except Exception as error:
            print(f"Price download failed for {ticker}: {error}")
            return pd.DataFrame()

    def get_1m(self, symbol):
        return self.get_candles(symbol, "1m", "1d")

    def get_5m(self, symbol):
        return self.get_candles(symbol, "5m", "1d")

    def today_only(self, df):
        """
        Return the latest available market-data session.

        On a normal trading day this is today's session.
        On weekends/holidays it is the most recent session returned
        by the data provider. This keeps paper/back-testing checks
        from becoming empty simply because the calendar date has no
        NSE candles.
        """
        if df is None or df.empty:
            return pd.DataFrame()

        result = df.copy()

        try:
            result["Datetime"] = pd.to_datetime(
                result["Datetime"], errors="coerce"
            )
            result = result.dropna(subset=["Datetime"])
            if result.empty:
                return pd.DataFrame()

            latest_date = result["Datetime"].dt.date.max()

            result = result[
                result["Datetime"].dt.date == latest_date
            ]

            return result.sort_values("Datetime").reset_index(drop=True)

        except Exception:
            return pd.DataFrame()

    def latest_candle(self, symbol, interval="1m"):
        df = self.get_candles(symbol, interval, "1d")
        if df.empty:
            return None
        return df.iloc[-1].to_dict()


if __name__ == "__main__":
    print("=" * 90)
    print("PRICE DATA ENGINE - YFINANCE")
    print("=" * 90)

    engine = PriceData()
    symbol = "RELIANCE"

    print("Test Stock        :", symbol)
    print("Yahoo Symbol      :", engine.yahoo_symbol(symbol))

    data_5m = engine.get_5m(symbol)
    print("5-Minute Candles  :", len(data_5m))
    if not data_5m.empty:
        print(data_5m.tail(5).to_string(index=False))

    data_1m = engine.get_1m(symbol)
    print("1-Minute Candles  :", len(data_1m))
    if not data_1m.empty:
        print(data_1m.tail(5).to_string(index=False))

    print("PRICE DATA ENGINE TEST COMPLETE")