"""
MARKET DIRECTION ENGINE
=======================

Purpose:
Determine the intraday direction of the overall market.

Simple Version 1 rule:

    Current Price > Day Open  -> BULLISH
    Current Price < Day Open  -> BEARISH

A small neutral zone is used around the open to avoid
constantly switching direction when price is almost unchanged.

The engine uses completed 5-minute candles.

Strategy:

BUY setups are allowed only when:
    Market = BULLISH

SELL setups are allowed only when:
    Market = BEARISH
"""

from datetime import time

import pandas as pd
import yfinance as yf


class MarketDirection:

    def __init__(self):

        # Yahoo Finance ticker used as broad-market reference.
        #
        # We first try the NIFTY 50 because Yahoo Finance
        # provides reliable intraday data for it.
        #
        # Our stock universe remains NIFTY LargeMidcap 250.

        self.market_ticker = "^NSEI"

        # Small neutral zone around the day's open.
        #
        # 0.05% means:
        # if price is extremely close to the open,
        # direction becomes NEUTRAL.

        self.neutral_percent = 0.05

    # ============================================================
    # CLEAN YFINANCE DATA
    # ============================================================

    def _clean_data(self, df):

        if df is None or df.empty:

            return pd.DataFrame()

        df = df.copy()

        # --------------------------------------------------------
        # Flatten MultiIndex
        # --------------------------------------------------------

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = [
                column[0]
                if isinstance(column, tuple)
                else column
                for column in df.columns
            ]

        # --------------------------------------------------------
        # Reset datetime index
        # --------------------------------------------------------

        df = df.reset_index()

        datetime_column = None

        for column in df.columns:

            if str(column).lower() in {
                "datetime",
                "date"
            }:

                datetime_column = column
                break

        if datetime_column is None:

            return pd.DataFrame()

        df = df.rename(
            columns={
                datetime_column: "Datetime"
            }
        )

        df["Datetime"] = pd.to_datetime(
            df["Datetime"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["Datetime"]
        )

        # --------------------------------------------------------
        # Convert timezone to India
        # --------------------------------------------------------

        try:

            if df["Datetime"].dt.tz is not None:

                df["Datetime"] = (
                    df["Datetime"]
                    .dt.tz_convert(
                        "Asia/Kolkata"
                    )
                )

        except Exception:

            pass

        # --------------------------------------------------------
        # Ensure OHLC numeric
        # --------------------------------------------------------

        for column in [
            "Open",
            "High",
            "Low",
            "Close"
        ]:

            if column not in df.columns:

                return pd.DataFrame()

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close"
            ]
        )

        return (
            df
            .sort_values("Datetime")
            .reset_index(drop=True)
        )

    # ============================================================
    # DOWNLOAD MARKET DATA
    # ============================================================

    def get_market_data(self):

        try:

            df = yf.download(
                tickers=self.market_ticker,
                period="1d",
                interval="5m",
                auto_adjust=False,
                progress=False,
                threads=False,
                prepost=False
            )

            return self._clean_data(
                df
            )

        except Exception as error:

            print(
                "Market data download failed:",
                error
            )

            return pd.DataFrame()

    # ============================================================
    # COMPLETED CANDLES
    # ============================================================

    def completed_candles(
        self,
        df,
        current_time=None
    ):

        if df is None or df.empty:

            return pd.DataFrame()

        result = df.copy()

        # During historical testing we simply use all
        # downloaded completed candles.

        if current_time is None:

            return result

        if isinstance(
            current_time,
            str
        ):

            current_time = pd.Timestamp(
                current_time
            )

        result = result[
            result["Datetime"]
            <= current_time
        ]

        return (
            result
            .reset_index(drop=True)
        )

    # ============================================================
    # GET DIRECTION
    # ============================================================

    def calculate_direction(
        self,
        df
    ):

        if df is None or df.empty:

            return {
                "direction": "UNKNOWN",
                "day_open": None,
                "current_price": None,
                "change": None,
                "change_percent": None
            }

        # --------------------------------------------------------
        # DAY OPEN
        # --------------------------------------------------------

        day_open = float(
            df.iloc[0]["Open"]
        )

        # --------------------------------------------------------
        # LATEST COMPLETED PRICE
        # --------------------------------------------------------

        current_price = float(
            df.iloc[-1]["Close"]
        )

        # --------------------------------------------------------
        # CHANGE
        # --------------------------------------------------------

        change = (
            current_price
            - day_open
        )

        if day_open == 0:

            change_percent = 0.0

        else:

            change_percent = (
                change
                / day_open
            ) * 100

        # --------------------------------------------------------
        # DIRECTION
        # --------------------------------------------------------

        if (
            change_percent
            > self.neutral_percent
        ):

            direction = "BULLISH"

        elif (
            change_percent
            < -self.neutral_percent
        ):

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        return {
            "direction": direction,
            "day_open": round(
                day_open,
                2
            ),
            "current_price": round(
                current_price,
                2
            ),
            "change": round(
                change,
                2
            ),
            "change_percent": round(
                change_percent,
                3
            )
        }

    # ============================================================
    # ANALYZE MARKET
    # ============================================================

    def analyze(self):

        df = self.get_market_data()

        if df.empty:

            return {
                "direction": "UNKNOWN",
                "day_open": None,
                "current_price": None,
                "change": None,
                "change_percent": None
            }

        return self.calculate_direction(
            df
        )

    # ============================================================
    # BUY ALLOWED
    # ============================================================

    def buy_allowed(self):

        result = self.analyze()

        return (
            result["direction"]
            == "BULLISH"
        )

    # ============================================================
    # SELL ALLOWED
    # ============================================================

    def sell_allowed(self):

        result = self.analyze()

        return (
            result["direction"]
            == "BEARISH"
        )


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("MARKET DIRECTION ENGINE")
    print("=" * 90)

    engine = MarketDirection()

    print(
        "Market Reference :",
        engine.market_ticker
    )

    print(
        "Neutral Zone     :",
        f"{engine.neutral_percent}%"
    )

    print()

    print(
        "Downloading 5-minute market data..."
    )

    data = engine.get_market_data()

    print(
        "Candles Loaded   :",
        len(data)
    )

    if not data.empty:

        print()

        print("LAST 5 CANDLES")
        print("-" * 90)

        columns = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close"
        ]

        print(
            data[
                columns
            ]
            .tail(5)
            .to_string(
                index=False
            )
        )

        print()

        result = (
            engine.calculate_direction(
                data
            )
        )

        print("MARKET DIRECTION")
        print("-" * 90)

        print(
            "Day Open         :",
            result["day_open"]
        )

        print(
            "Current Price    :",
            result["current_price"]
        )

        print(
            "Change           :",
            result["change"]
        )

        print(
            "Change %         :",
            result["change_percent"]
        )

        print(
            "Direction        :",
            result["direction"]
        )

        print()

        print(
            "BUY Allowed      :",
            result["direction"]
            == "BULLISH"
        )

        print(
            "SELL Allowed     :",
            result["direction"]
            == "BEARISH"
        )

    print()

    print("=" * 90)

    if not data.empty:

        print(
            "MARKET DIRECTION ENGINE TEST PASSED"
        )

    else:

        print(
            "MARKET DIRECTION ENGINE TEST WARNING"
        )

    print("=" * 90)