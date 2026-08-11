"""
MARKET DIRECTION ENGINE
=======================

Determine intraday NIFTY direction using Yahoo Finance.
"""

import pandas as pd
import yfinance as yf


class MarketDirection:

    def __init__(self):
        self.market_ticker = "^NSEI"
        self.neutral_percent = 0.05
        self.download_timeout = 10

    def _clean_data(self, df):
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                column[0] if isinstance(column, tuple) else column
                for column in df.columns
            ]

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

        for column in ["Open", "High", "Low", "Close"]:
            if column not in df.columns:
                return pd.DataFrame()
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        return df.sort_values("Datetime").reset_index(drop=True)

    def get_market_data(self):
        try:
            df = yf.download(
                tickers=self.market_ticker,
                period="1d",
                interval="5m",
                auto_adjust=False,
                progress=False,
                threads=False,
                prepost=False,
                timeout=self.download_timeout,
            )
            return self._clean_data(df)
        except Exception as error:
            print("Market data download failed:", error)
            return pd.DataFrame()

    def completed_candles(self, df, current_time=None):
        if df is None or df.empty:
            return pd.DataFrame()

        result = df.copy()
        if current_time is None:
            return result

        if isinstance(current_time, str):
            current_time = pd.Timestamp(current_time)

        result = result[result["Datetime"] <= current_time]
        return result.reset_index(drop=True)

    def calculate_direction(self, df):
        if df is None or df.empty:
            return {
                "direction": "UNKNOWN",
                "day_open": None,
                "current_price": None,
                "change": None,
                "change_percent": None,
            }

        day_open = float(df.iloc[0]["Open"])
        current_price = float(df.iloc[-1]["Close"])
        change = current_price - day_open
        change_percent = 0.0 if day_open == 0 else (change / day_open) * 100

        if change_percent > self.neutral_percent:
            direction = "BULLISH"
        elif change_percent < -self.neutral_percent:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return {
            "direction": direction,
            "day_open": round(day_open, 2),
            "current_price": round(current_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 3),
        }

    def analyze(self):
        df = self.get_market_data()
        if df.empty:
            return {
                "direction": "UNKNOWN",
                "day_open": None,
                "current_price": None,
                "change": None,
                "change_percent": None,
            }
        return self.calculate_direction(df)

    def buy_allowed(self):
        return self.analyze()["direction"] == "BULLISH"

    def sell_allowed(self):
        return self.analyze()["direction"] == "BEARISH"


if __name__ == "__main__":
    print("=" * 90)
    print("MARKET DIRECTION ENGINE")
    print("=" * 90)

    engine = MarketDirection()
    print("Market Reference :", engine.market_ticker)
    print("Neutral Zone     :", f"{engine.neutral_percent}%")
    print("Downloading 5-minute market data...")

    data = engine.get_market_data()
    print("Candles Loaded   :", len(data))

    if not data.empty:
        print(data[["Datetime", "Open", "High", "Low", "Close"]].tail(5).to_string(index=False))
        result = engine.calculate_direction(data)
        print("MARKET DIRECTION")
        print("Day Open         :", result["day_open"])
        print("Current Price    :", result["current_price"])
        print("Change           :", result["change"])
        print("Change %         :", result["change_percent"])
        print("Direction        :", result["direction"])
        print("BUY Allowed      :", result["direction"] == "BULLISH")
        print("SELL Allowed     :", result["direction"] == "BEARISH")

    print("MARKET DIRECTION ENGINE TEST COMPLETE")
