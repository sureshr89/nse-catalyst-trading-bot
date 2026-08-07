"""
PRICE DATA ENGINE
=================

Free market-data source: yfinance

Purpose:
1. Convert NSE symbols to Yahoo Finance symbols.
2. Download 1-minute candles for entry confirmation.
3. Download 5-minute candles for setup/pullback.
4. Download today's intraday candles.
5. Clean Yahoo Finance data into a standard format.

Examples:
    RELIANCE -> RELIANCE.NS
    INFY     -> INFY.NS
    ABB      -> ABB.NS

Strategy use:
    5-minute candles = setup / pullback
    1-minute candles = final breakout confirmation

Important:
    yfinance is being used for development and paper trading.
"""

from datetime import datetime

import pandas as pd
import yfinance as yf


class PriceData:

    def __init__(self):

        self.valid_intervals = {
            "1m",
            "5m"
        }

    # ============================================================
    # NSE -> YAHOO SYMBOL
    # ============================================================

    def yahoo_symbol(self, symbol):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        # Already Yahoo-formatted
        if symbol.endswith(".NS"):
            return symbol

        return f"{symbol}.NS"

    # ============================================================
    # CLEAN DOWNLOADED DATA
    # ============================================================

    def _clean_data(self, df):

        if df is None:
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        df = df.copy()

        # --------------------------------------------------------
        # yfinance can sometimes return MultiIndex columns.
        # Flatten them safely.
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
        # Standard column names
        # --------------------------------------------------------

        rename_map = {}

        for column in df.columns:

            name = str(column).strip()

            lower = name.lower()

            if lower == "open":
                rename_map[column] = "Open"

            elif lower == "high":
                rename_map[column] = "High"

            elif lower == "low":
                rename_map[column] = "Low"

            elif lower == "close":
                rename_map[column] = "Close"

            elif lower == "volume":
                rename_map[column] = "Volume"

        df = df.rename(
            columns=rename_map
        )

        required = [
            "Open",
            "High",
            "Low",
            "Close"
        ]

        for column in required:

            if column not in df.columns:

                print(
                    f"Missing price column: {column}"
                )

                return pd.DataFrame()

        # --------------------------------------------------------
        # Convert index into Datetime column
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

            print(
                "Unable to find datetime column."
            )

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
        # Numeric conversion
        # --------------------------------------------------------

        numeric_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for column in numeric_columns:

            if column in df.columns:

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

        # --------------------------------------------------------
        # Keep only useful columns
        # --------------------------------------------------------

        keep_columns = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close"
        ]

        if "Volume" in df.columns:
            keep_columns.append("Volume")

        df = df[
            keep_columns
        ]

        df = (
            df
            .sort_values("Datetime")
            .drop_duplicates(
                subset=["Datetime"]
            )
            .reset_index(drop=True)
        )

        return df

    # ============================================================
    # DOWNLOAD CANDLES
    # ============================================================

    def get_candles(
        self,
        symbol,
        interval="5m",
        period="1d"
    ):

        if interval not in self.valid_intervals:

            raise ValueError(
                f"Unsupported interval: {interval}"
            )

        ticker = self.yahoo_symbol(
            symbol
        )

        try:

            df = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
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
                f"Price download failed "
                f"for {ticker}: {error}"
            )

            return pd.DataFrame()

    # ============================================================
    # 1-MINUTE DATA
    # ============================================================

    def get_1m(self, symbol):

        return self.get_candles(
            symbol=symbol,
            interval="1m",
            period="1d"
        )

    # ============================================================
    # 5-MINUTE DATA
    # ============================================================

    def get_5m(self, symbol):

        return self.get_candles(
            symbol=symbol,
            interval="5m",
            period="1d"
        )

    # ============================================================
    # TODAY ONLY
    # ============================================================

    def today_only(self, df):

        if df is None or df.empty:

            return pd.DataFrame()

        result = df.copy()

        now = datetime.now().date()

        try:

            dates = (
                result["Datetime"]
                .dt.date
            )

            result = result[
                dates == now
            ]

        except Exception:

            return pd.DataFrame()

        return (
            result
            .reset_index(drop=True)
        )

    # ============================================================
    # LATEST COMPLETED CANDLE
    # ============================================================

    def latest_candle(
        self,
        symbol,
        interval="1m"
    ):

        df = self.get_candles(
            symbol=symbol,
            interval=interval,
            period="1d"
        )

        if df.empty:

            return None

        return (
            df.iloc[-1]
            .to_dict()
        )


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("PRICE DATA ENGINE - YFINANCE")
    print("=" * 90)

    engine = PriceData()

    symbol = "RELIANCE"

    print(
        "Test Stock        :",
        symbol
    )

    print(
        "Yahoo Symbol      :",
        engine.yahoo_symbol(symbol)
    )

    print()

    # ------------------------------------------------------------
    # TEST 5-MINUTE DATA
    # ------------------------------------------------------------

    print(
        "Downloading 5-minute candles..."
    )

    data_5m = engine.get_5m(
        symbol
    )

    print(
        "5-Minute Candles  :",
        len(data_5m)
    )

    if not data_5m.empty:

        print()
        print("LAST 5-MINUTE CANDLES")
        print("-" * 90)

        print(
            data_5m.tail(5).to_string(
                index=False
            )
        )

    print()

    # ------------------------------------------------------------
    # TEST 1-MINUTE DATA
    # ------------------------------------------------------------

    print(
        "Downloading 1-minute candles..."
    )

    data_1m = engine.get_1m(
        symbol
    )

    print(
        "1-Minute Candles  :",
        len(data_1m)
    )

    if not data_1m.empty:

        print()
        print("LAST 1-MINUTE CANDLES")
        print("-" * 90)

        print(
            data_1m.tail(5).to_string(
                index=False
            )
        )

    print()

    # ------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------

    print("=" * 90)

    if (
        not data_5m.empty
        and not data_1m.empty
    ):

        print(
            "PRICE DATA ENGINE TEST PASSED"
        )

    else:

        print(
            "PRICE DATA ENGINE TEST WARNING"
        )

        print(
            "No intraday data was returned "
            "for one or more intervals."
        )

    print("=" * 90)