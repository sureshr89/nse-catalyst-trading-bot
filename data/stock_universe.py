"""
NIFTY LargeMidcap 250 Stock Universe

Purpose:
1. Download the official NIFTY LargeMidcap 250 constituent list.
2. Extract NSE stock symbols.
3. Save a local CSV copy.
4. Allow the trading scanner to load the stock universe.

The strategy will scan only these stocks.
"""

from pathlib import Path
from io import StringIO

import pandas as pd
import requests


class StockUniverse:

    def __init__(self):

        # Official NSE Indices constituent CSV
        self.url = (
            "https://www.niftyindices.com/"
            "IndexConstituent/ind_niftylargemidcap250list.csv"
        )

        # Local storage
        self.data_folder = Path("data")
        self.output_file = self.data_folder / "nifty_largemidcap_250.csv"

        # Make sure data folder exists
        self.data_folder.mkdir(parents=True, exist_ok=True)

        # Browser-like headers
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

    # ============================================================
    # DOWNLOAD
    # ============================================================

    def download(self):

        print("Downloading NIFTY LargeMidcap 250 constituents...")

        try:

            response = requests.get(
                self.url,
                headers=self.headers,
                timeout=30
            )

            print("HTTP Status :", response.status_code)

            if response.status_code != 200:

                print(
                    "Unable to download constituent list."
                )

                return None

            if not response.text.strip():

                print("Downloaded file is empty.")

                return None

            df = pd.read_csv(
                StringIO(response.text)
            )

            return df

        except requests.RequestException as error:

            print("Download error :", error)

            return None

        except Exception as error:

            print("Unexpected error :", error)

            return None

    # ============================================================
    # CLEAN DATA
    # ============================================================

    def clean(self, df):

        if df is None:

            return None

        if df.empty:

            print("Constituent dataframe is empty.")

            return None

        # Remove unwanted spaces from column names
        df.columns = [
            str(column).strip()
            for column in df.columns
        ]

        print("CSV Columns :", df.columns.tolist())

        # Find Symbol column safely
        symbol_column = None

        for column in df.columns:

            if column.lower() == "symbol":

                symbol_column = column
                break

        if symbol_column is None:

            print("ERROR: Symbol column not found.")

            return None

        # Clean symbols
        df[symbol_column] = (
            df[symbol_column]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # Remove empty symbols
        df = df[
            df[symbol_column].notna()
        ]

        df = df[
            df[symbol_column] != ""
        ]

        # Remove duplicates
        df = df.drop_duplicates(
            subset=[symbol_column]
        )

        # Rename consistently
        if symbol_column != "Symbol":

            df = df.rename(
                columns={
                    symbol_column: "Symbol"
                }
            )

        # Reset index
        df = df.reset_index(drop=True)

        return df

    # ============================================================
    # SAVE
    # ============================================================

    def save(self, df):

        if df is None:

            return False

        if df.empty:

            return False

        df.to_csv(
            self.output_file,
            index=False
        )

        print(
            "Saved universe :",
            self.output_file
        )

        return True

    # ============================================================
    # LOAD LOCAL COPY
    # ============================================================

    def load_local(self):

        if not self.output_file.exists():

            print(
                "Local universe file does not exist."
            )

            return None

        try:

            df = pd.read_csv(
                self.output_file
            )

            df.columns = [
                str(column).strip()
                for column in df.columns
            ]

            if "Symbol" not in df.columns:

                print(
                    "Symbol column missing from local file."
                )

                return None

            df["Symbol"] = (
                df["Symbol"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            df = df.drop_duplicates(
                subset=["Symbol"]
            )

            df = df.reset_index(drop=True)

            return df

        except Exception as error:

            print(
                "Unable to read local universe :",
                error
            )

            return None

    # ============================================================
    # GET SYMBOLS
    # ============================================================

    def get_symbols(self, refresh=True):

        df = None

        # First try fresh official data
        if refresh:

            downloaded = self.download()

            if downloaded is not None:

                cleaned = self.clean(
                    downloaded
                )

                if cleaned is not None:

                    if not cleaned.empty:

                        self.save(cleaned)

                        df = cleaned

        # Fallback to local copy
        if df is None:

            print(
                "Trying local universe copy..."
            )

            df = self.load_local()

        if df is None:

            return []

        symbols = (
            df["Symbol"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .unique()
            .tolist()
        )

        return symbols


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 80)

    print(
        "NIFTY LARGEMIDCAP 250 STOCK UNIVERSE"
    )

    print("=" * 80)

    universe = StockUniverse()

    symbols = universe.get_symbols(
        refresh=True
    )

    print()
    print("=" * 80)

    print(
        "TOTAL STOCKS LOADED :",
        len(symbols)
    )

    print("=" * 80)

    if symbols:

        print()
        print("FIRST 20 STOCKS")
        print("-" * 80)

        for number, symbol in enumerate(
            symbols[:20],
            start=1
        ):

            print(
                f"{number:3}. {symbol}"
            )

        print()

        if len(symbols) == 250:

            print(
                "UNIVERSE TEST PASSED - EXACTLY 250 STOCKS"
            )

        else:

            print(
                "WARNING: Expected 250 stocks, "
                f"but received {len(symbols)}."
            )

    else:

        print(
            "UNIVERSE TEST FAILED - NO STOCKS LOADED"
        )

    print("=" * 80)