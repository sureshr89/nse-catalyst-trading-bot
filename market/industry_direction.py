"""
INDUSTRY DIRECTION ENGINE
=========================

Purpose:
Determine BULLISH / BEARISH / NEUTRAL direction for each
industry in the NIFTY LargeMidcap 250 universe.

Method:
1. Load the 250-stock universe.
2. Download 5-minute data from Yahoo Finance in batches.
3. Compare each stock's latest close with its day open.
4. Classify each stock:
       > +0.05% = BULLISH
       < -0.05% = BEARISH
       otherwise = NEUTRAL
5. Calculate breadth inside each industry.
6. Industry becomes:
       >= 60% bullish stocks = BULLISH
       >= 60% bearish stocks = BEARISH
       otherwise = NEUTRAL

This is a breadth-based industry filter.

Example:
Information Technology:
    10 bullish
     3 bearish
     1 neutral

Bullish % = 71.4%

Industry = BULLISH
"""

from pathlib import Path

import pandas as pd
import yfinance as yf


class IndustryDirection:

    def __init__(
        self,
        universe_file="data/nifty_largemidcap_250.csv"
    ):

        self.universe_file = Path(
            universe_file
        )

        # Stock neutral zone around day open
        self.stock_neutral_percent = 0.05

        # Minimum percentage of stocks required
        # for industry directional confirmation
        self.industry_threshold = 60.0

        self.universe = pd.DataFrame()

        self.stock_results = pd.DataFrame()

        self.industry_results = pd.DataFrame()

        self._load_universe()

    # ============================================================
    # LOAD UNIVERSE
    # ============================================================

    def _load_universe(self):

        if not self.universe_file.exists():

            raise FileNotFoundError(
                f"Universe file not found: "
                f"{self.universe_file}"
            )

        df = pd.read_csv(
            self.universe_file
        )

        df.columns = [
            str(column).strip()
            for column in df.columns
        ]

        required = {
            "Symbol",
            "Industry"
        }

        missing = (
            required
            - set(df.columns)
        )

        if missing:

            raise ValueError(
                f"Missing columns: "
                f"{sorted(missing)}"
            )

        df["Symbol"] = (
            df["Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df["Industry"] = (
            df["Industry"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.strip()
        )

        df = (
            df
            .drop_duplicates(
                subset=["Symbol"]
            )
            .reset_index(drop=True)
        )

        self.universe = df[
            [
                "Symbol",
                "Industry"
            ]
        ].copy()

    # ============================================================
    # YAHOO SYMBOL
    # ============================================================

    def yahoo_symbol(
        self,
        symbol
    ):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if symbol.endswith(".NS"):

            return symbol

        return f"{symbol}.NS"

    # ============================================================
    # DOWNLOAD 250 STOCKS
    # ============================================================

    def download_market_data(self):

        symbols = (
            self.universe["Symbol"]
            .tolist()
        )

        yahoo_symbols = [
            self.yahoo_symbol(symbol)
            for symbol in symbols
        ]

        print(
            "Downloading 5-minute data "
            f"for {len(yahoo_symbols)} stocks..."
        )

        try:

            data = yf.download(
                tickers=yahoo_symbols,
                period="1d",
                interval="5m",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
                prepost=False
            )

            return data

        except Exception as error:

            print(
                "Industry market-data "
                f"download failed: {error}"
            )

            return pd.DataFrame()

    # ============================================================
    # EXTRACT STOCK DATA
    # ============================================================

    def _extract_stock_data(
        self,
        data,
        symbol
    ):

        if data is None or data.empty:

            return pd.DataFrame()

        ticker = self.yahoo_symbol(
            symbol
        )

        try:

            # ----------------------------------------------------
            # MultiIndex format expected for multiple tickers
            # ----------------------------------------------------

            if isinstance(
                data.columns,
                pd.MultiIndex
            ):

                level_0 = (
                    data.columns
                    .get_level_values(0)
                )

                level_1 = (
                    data.columns
                    .get_level_values(1)
                )

                # Typical yfinance format:
                #
                # Price / Ticker
                #
                # ('Open', 'RELIANCE.NS')
                # ('Close', 'RELIANCE.NS')

                if ticker in level_1:

                    stock = (
                        data
                        .xs(
                            ticker,
                            axis=1,
                            level=1
                        )
                        .copy()
                    )

                # Handle opposite MultiIndex orientation
                elif ticker in level_0:

                    stock = (
                        data
                        .xs(
                            ticker,
                            axis=1,
                            level=0
                        )
                        .copy()
                    )

                else:

                    return pd.DataFrame()

            else:

                stock = data.copy()

            # ----------------------------------------------------
            # Remove completely empty candles
            # ----------------------------------------------------

            stock = stock.dropna(
                how="all"
            )

            if stock.empty:

                return pd.DataFrame()

            required = [
                "Open",
                "High",
                "Low",
                "Close"
            ]

            for column in required:

                if column not in stock.columns:

                    return pd.DataFrame()

            # ----------------------------------------------------
            # Numeric conversion
            # ----------------------------------------------------

            for column in required:

                stock[column] = (
                    pd.to_numeric(
                        stock[column],
                        errors="coerce"
                    )
                )

            stock = stock.dropna(
                subset=[
                    "Open",
                    "Close"
                ]
            )

            return stock

        except Exception:

            return pd.DataFrame()

    # ============================================================
    # CLASSIFY ONE STOCK
    # ============================================================

    def classify_stock(
        self,
        data,
        symbol,
        industry
    ):

        stock = self._extract_stock_data(
            data,
            symbol
        )

        if stock.empty:

            return {
                "Symbol": symbol,
                "Industry": industry,
                "DayOpen": None,
                "LastPrice": None,
                "ChangePercent": None,
                "Direction": "NO_DATA"
            }

        day_open = float(
            stock.iloc[0]["Open"]
        )

        last_price = float(
            stock.iloc[-1]["Close"]
        )

        if day_open == 0:

            change_percent = 0.0

        else:

            change_percent = (
                (
                    last_price
                    - day_open
                )
                / day_open
            ) * 100

        if (
            change_percent
            > self.stock_neutral_percent
        ):

            direction = "BULLISH"

        elif (
            change_percent
            < -self.stock_neutral_percent
        ):

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        return {
            "Symbol": symbol,
            "Industry": industry,
            "DayOpen": round(
                day_open,
                2
            ),
            "LastPrice": round(
                last_price,
                2
            ),
            "ChangePercent": round(
                change_percent,
                3
            ),
            "Direction": direction
        }

    # ============================================================
    # ANALYZE ALL STOCKS
    # ============================================================

    def analyze_stocks(
        self,
        data
    ):

        results = []

        for _, row in (
            self.universe.iterrows()
        ):

            result = self.classify_stock(
                data=data,
                symbol=row["Symbol"],
                industry=row["Industry"]
            )

            results.append(
                result
            )

        self.stock_results = (
            pd.DataFrame(
                results
            )
        )

        return self.stock_results

    # ============================================================
    # CALCULATE INDUSTRY DIRECTION
    # ============================================================

    def calculate_industries(
        self,
        stock_results
    ):

        results = []

        industries = sorted(
            self.universe[
                "Industry"
            ]
            .unique()
            .tolist()
        )

        for industry in industries:

            group = stock_results[
                stock_results["Industry"]
                == industry
            ].copy()

            total_constituents = len(
                group
            )

            valid = group[
                group["Direction"]
                != "NO_DATA"
            ]

            valid_count = len(
                valid
            )

            bullish = int(
                (
                    valid["Direction"]
                    == "BULLISH"
                ).sum()
            )

            bearish = int(
                (
                    valid["Direction"]
                    == "BEARISH"
                ).sum()
            )

            neutral = int(
                (
                    valid["Direction"]
                    == "NEUTRAL"
                ).sum()
            )

            no_data = (
                total_constituents
                - valid_count
            )

            if valid_count == 0:

                bullish_percent = 0.0
                bearish_percent = 0.0
                neutral_percent = 0.0

                direction = "NO_DATA"

            else:

                bullish_percent = (
                    bullish
                    / valid_count
                ) * 100

                bearish_percent = (
                    bearish
                    / valid_count
                ) * 100

                neutral_percent = (
                    neutral
                    / valid_count
                ) * 100

                if (
                    bullish_percent
                    >= self.industry_threshold
                ):

                    direction = "BULLISH"

                elif (
                    bearish_percent
                    >= self.industry_threshold
                ):

                    direction = "BEARISH"

                else:

                    direction = "NEUTRAL"

            results.append(
                {
                    "Industry": industry,

                    "Total": total_constituents,

                    "Valid": valid_count,

                    "Bullish": bullish,

                    "Bearish": bearish,

                    "Neutral": neutral,

                    "NoData": no_data,

                    "BullishPercent": round(
                        bullish_percent,
                        1
                    ),

                    "BearishPercent": round(
                        bearish_percent,
                        1
                    ),

                    "NeutralPercent": round(
                        neutral_percent,
                        1
                    ),

                    "Direction": direction
                }
            )

        self.industry_results = (
            pd.DataFrame(
                results
            )
        )

        return self.industry_results

    # ============================================================
    # FULL ANALYSIS
    # ============================================================

    def analyze(self):

        data = self.download_market_data()

        if data is None or data.empty:

            return (
                pd.DataFrame(),
                pd.DataFrame()
            )

        stock_results = (
            self.analyze_stocks(
                data
            )
        )

        industry_results = (
            self.calculate_industries(
                stock_results
            )
        )

        return (
            stock_results,
            industry_results
        )

    # ============================================================
    # GET ONE INDUSTRY DIRECTION
    # ============================================================

    def get_industry_direction(
        self,
        industry
    ):

        if self.industry_results.empty:

            return "UNKNOWN"

        match = self.industry_results[
            self.industry_results[
                "Industry"
            ] == industry
        ]

        if match.empty:

            return "UNKNOWN"

        return (
            match.iloc[0][
                "Direction"
            ]
        )

    # ============================================================
    # GET STOCK DIRECTION
    # ============================================================

    def get_stock_direction(
        self,
        symbol
    ):

        if self.stock_results.empty:

            return "UNKNOWN"

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        match = self.stock_results[
            self.stock_results[
                "Symbol"
            ] == symbol
        ]

        if match.empty:

            return "UNKNOWN"

        return (
            match.iloc[0][
                "Direction"
            ]
        )


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 110)

    print(
        "INDUSTRY DIRECTION ENGINE"
    )

    print("=" * 110)

    engine = IndustryDirection()

    print(
        "Stocks in Universe      :",
        len(engine.universe)
    )

    print(
        "Industries              :",
        engine.universe[
            "Industry"
        ].nunique()
    )

    print(
        "Stock Neutral Zone      :",
        f"{engine.stock_neutral_percent}%"
    )

    print(
        "Industry Threshold      :",
        f"{engine.industry_threshold}%"
    )

    print()

    stock_results, industry_results = (
        engine.analyze()
    )

    print()

    if stock_results.empty:

        print(
            "No stock data available."
        )

    else:

        no_data_count = int(
            (
                stock_results[
                    "Direction"
                ] == "NO_DATA"
            ).sum()
        )

        print(
            "Stocks Analyzed         :",
            len(stock_results)
        )

        print(
            "Stocks Without Data     :",
            no_data_count
        )

        print()

        print(
            "INDUSTRY BREADTH"
        )

        print("-" * 110)

        display_columns = [
            "Industry",
            "Total",
            "Valid",
            "Bullish",
            "Bearish",
            "Neutral",
            "NoData",
            "BullishPercent",
            "BearishPercent",
            "Direction"
        ]

        print(
            industry_results[
                display_columns
            ]
            .to_string(
                index=False
            )
        )

        print()

        print(
            "SAMPLE STOCK DIRECTIONS"
        )

        print("-" * 110)

        sample_symbols = [
            "RELIANCE",
            "INFY",
            "ABB",
            "SUNPHARMA",
            "ADANIPOWER",
            "ACC"
        ]

        for symbol in sample_symbols:

            match = stock_results[
                stock_results[
                    "Symbol"
                ] == symbol
            ]

            if match.empty:

                print(
                    f"{symbol:15} NOT FOUND"
                )

                continue

            row = match.iloc[0]

            print(
                f"{symbol:15} "
                f"{row['Industry']:35} "
                f"{str(row['Direction']):10} "
                f"{str(row['ChangePercent']):>8}%"
            )

    print()

    print("=" * 110)

    if (
        not stock_results.empty
        and not industry_results.empty
    ):

        print(
            "INDUSTRY DIRECTION ENGINE TEST PASSED"
        )

    else:

        print(
            "INDUSTRY DIRECTION ENGINE TEST WARNING"
        )

    print("=" * 110)