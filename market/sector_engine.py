"""
SECTOR / INDUSTRY ENGINE
========================

Uses the official Industry classification contained in the
NIFTY LargeMidcap 250 constituent file.

We do NOT manually guess sectors.

Each stock keeps its official Industry group.

Examples:
    INFY       -> Information Technology
    SUNPHARMA  -> Healthcare
    RELIANCE   -> Oil Gas & Consumable Fuels
    ABB        -> Capital Goods

Later these groups will be used for industry/sector alignment.
"""

from pathlib import Path

import pandas as pd


class SectorEngine:

    def __init__(
        self,
        universe_file="data/nifty_largemidcap_250.csv"
    ):

        self.universe_file = Path(universe_file)

        self.df = None

        self.stock_sector_map = {}

        self._load_data()

    # ============================================================
    # LOAD DATA
    # ============================================================

    def _load_data(self):

        if not self.universe_file.exists():

            raise FileNotFoundError(
                f"Universe file not found: {self.universe_file}"
            )

        self.df = pd.read_csv(
            self.universe_file
        )

        # Clean column names
        self.df.columns = [
            str(column).strip()
            for column in self.df.columns
        ]

        required_columns = {
            "Symbol",
            "Industry"
        }

        missing_columns = (
            required_columns
            - set(self.df.columns)
        )

        if missing_columns:

            raise ValueError(
                "Missing required columns: "
                f"{sorted(missing_columns)}"
            )

        # --------------------------------------------------------
        # CLEAN SYMBOL
        # --------------------------------------------------------

        self.df["Symbol"] = (
            self.df["Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # --------------------------------------------------------
        # CLEAN INDUSTRY
        # --------------------------------------------------------

        self.df["Industry"] = (
            self.df["Industry"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.strip()
        )

        # Remove accidental blank industries
        self.df.loc[
            self.df["Industry"] == "",
            "Industry"
        ] = "UNKNOWN"

        # --------------------------------------------------------
        # REMOVE DUPLICATE SYMBOLS
        # --------------------------------------------------------

        self.df = (
            self.df
            .drop_duplicates(
                subset=["Symbol"]
            )
            .reset_index(drop=True)
        )

        # --------------------------------------------------------
        # BUILD STOCK -> INDUSTRY MAP
        # --------------------------------------------------------

        self.stock_sector_map = {

            row["Symbol"]: row["Industry"]

            for _, row in self.df.iterrows()
        }

    # ============================================================
    # GET SECTOR / INDUSTRY
    # ============================================================

    def get_sector(self, symbol):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        industry = self.stock_sector_map.get(
            symbol
        )

        if industry is None:

            return {
                "symbol": symbol,
                "sector": "UNKNOWN",
                "industry": "UNKNOWN",
                "found": False
            }

        return {
            "symbol": symbol,

            # We use official Industry as our trading group.
            "sector": industry,

            "industry": industry,

            "found": True
        }

    # ============================================================
    # GET INDUSTRY
    # ============================================================

    def get_industry(self, symbol):

        result = self.get_sector(
            symbol
        )

        return result["industry"]

    # ============================================================
    # GET STOCKS IN INDUSTRY
    # ============================================================

    def get_sector_stocks(self, sector):

        sector = (
            str(sector)
            .strip()
            .lower()
        )

        stocks = []

        for symbol, industry in (
            self.stock_sector_map.items()
        ):

            if industry.lower() == sector:

                stocks.append(
                    symbol
                )

        return sorted(stocks)

    # ============================================================
    # GET ALL INDUSTRIES
    # ============================================================

    def get_all_sectors(self):

        sectors = (
            self.df["Industry"]
            .dropna()
            .unique()
            .tolist()
        )

        return sorted(
            sectors
        )

    # ============================================================
    # SECTOR COUNT
    # ============================================================

    def get_sector_count(self):

        return len(
            self.get_all_sectors()
        )

    # ============================================================
    # UNKNOWN STOCKS
    # ============================================================

    def get_unknown_stocks(self):

        unknown_df = self.df[
            self.df["Industry"].str.upper()
            == "UNKNOWN"
        ]

        return (
            unknown_df["Symbol"]
            .tolist()
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self):

        return (
            self.df["Industry"]
            .value_counts()
        )

    # ============================================================
    # FULL TABLE
    # ============================================================

    def get_table(self):

        return self.df[
            [
                "Symbol",
                "Industry"
            ]
        ].copy()


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("SECTOR / INDUSTRY ENGINE")
    print("=" * 90)

    engine = SectorEngine()

    print(
        "Stocks Loaded       :",
        len(engine.stock_sector_map)
    )

    print(
        "Industry Groups     :",
        engine.get_sector_count()
    )

    print(
        "Unknown Industries  :",
        len(engine.get_unknown_stocks())
    )

    print()

    print("INDUSTRY SUMMARY")
    print("-" * 90)

    print(
        engine.summary().to_string()
    )

    print()

    print("SAMPLE STOCKS")
    print("-" * 90)

    # Use actual symbols from our downloaded universe.
    sample_symbols = [
        "ABB",
        "RELIANCE",
        "INFY",
        "SUNPHARMA",
        "ADANIPOWER",
        "ACC"
    ]

    for symbol in sample_symbols:

        result = engine.get_sector(
            symbol
        )

        print(
            f"{symbol:15} "
            f"Industry: {result['industry']}"
        )

    print()

    print("=" * 90)

    if (
        len(engine.stock_sector_map) == 250
        and len(engine.get_unknown_stocks()) == 0
    ):

        print(
            "SECTOR ENGINE TEST PASSED"
        )

    else:

        print(
            "SECTOR ENGINE TEST WARNING"
        )

    print("=" * 90)