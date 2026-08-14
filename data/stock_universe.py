"""NIFTY 500 scanner universe."""
from io import StringIO
from pathlib import Path

import pandas as pd
import requests


class StockUniverse:
    MIN_EXPECTED_STOCKS = 450

    def __init__(self):
        self.urls = {
            "NIFTY500": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        }
        self.data_folder = Path("data")
        self.output_file = self.data_folder / "nifty500.csv"
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
            "Accept": "text/csv,*/*",
            "Referer": "https://www.niftyindices.com/",
        }

    def _download(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code != 200 or not response.text.strip():
                return None
            return pd.read_csv(StringIO(response.text))
        except Exception as error:
            print("Universe download error:", error)
            return None

    @staticmethod
    def _clean(df):
        if df is None or df.empty:
            return None
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        symbol_col = next((c for c in df.columns if c.lower() == "symbol"), None)
        if symbol_col is None:
            return None
        df[symbol_col] = df[symbol_col].astype(str).str.strip().str.upper()
        df = df[df[symbol_col].ne("")].drop_duplicates(symbol_col)
        if symbol_col != "Symbol":
            df = df.rename(columns={symbol_col: "Symbol"})
        if "Industry" not in df.columns:
            df["Industry"] = "UNKNOWN"
        return df.reset_index(drop=True)

    def download(self):
        df = self._clean(self._download(self.urls["NIFTY500"]))
        if df is None or df.empty:
            return None
        df["Universe"] = "NIFTY500"
        if len(df) < self.MIN_EXPECTED_STOCKS:
            print("NIFTY 500 universe rejected: only", len(df), "stocks")
            return None
        return df

    def save(self, df):
        if df is None or df.empty or len(df) < self.MIN_EXPECTED_STOCKS:
            return False
        df.to_csv(self.output_file, index=False)
        return True

    def load_local(self):
        if not self.output_file.exists():
            return None
        try:
            df = pd.read_csv(self.output_file)
            df.columns = [str(c).strip() for c in df.columns]
            if "Symbol" not in df.columns:
                return None
            df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
            if "Industry" not in df.columns:
                df["Industry"] = "UNKNOWN"
            df = df.drop_duplicates("Symbol").reset_index(drop=True)
            return df if len(df) >= self.MIN_EXPECTED_STOCKS else None
        except Exception:
            return None

    def get_dataframe(self, refresh=True):
        df = self.download() if refresh else None
        if df is None:
            df = self.load_local()
        if df is None:
            return pd.DataFrame(columns=["Symbol", "Industry", "Universe"])
        self.save(df)
        return df

    def get_symbols(self, refresh=True):
        df = self.get_dataframe(refresh=refresh)
        return df["Symbol"].dropna().astype(str).str.upper().unique().tolist()


if __name__ == "__main__":
    symbols = StockUniverse().get_symbols(refresh=True)
    print("NIFTY 500 stocks loaded:", len(symbols))
