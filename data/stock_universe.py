"""NIFTY 100 stock universe used by the paper strategy."""
from pathlib import Path
from io import StringIO
import pandas as pd
import requests


class StockUniverse:
    MIN_EXPECTED_STOCKS = 95

    def __init__(self):
        self.url = "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv"
        self.data_folder = Path("data")
        self.output_file = self.data_folder / "nifty100.csv"
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
            "Accept": "text/csv,*/*",
            "Referer": "https://www.niftyindices.com/",
        }

    def download(self):
        try:
            response = requests.get(self.url, headers=self.headers, timeout=30)
            if response.status_code != 200 or not response.text.strip():
                return None
            return pd.read_csv(StringIO(response.text))
        except Exception as error:
            print("NIFTY 100 download error:", error)
            return None

    def clean(self, df):
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
        if len(df) < self.MIN_EXPECTED_STOCKS:
            print(
                "NIFTY 100 universe rejected: only",
                len(df), "stocks; expected at least", self.MIN_EXPECTED_STOCKS,
            )
            return None
        return df.reset_index(drop=True)

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
            if len(df) < self.MIN_EXPECTED_STOCKS:
                print(
                    "Local NIFTY 100 universe rejected: only",
                    len(df), "stocks; expected at least", self.MIN_EXPECTED_STOCKS,
                )
                return None
            return df
        except Exception:
            return None

    def get_dataframe(self, refresh=True):
        df = self.clean(self.download()) if refresh else None
        if df is None:
            df = self.load_local()
        if df is None:
            return pd.DataFrame(columns=["Symbol", "Industry"])
        self.save(df)
        return df

    def get_symbols(self, refresh=True):
        df = self.get_dataframe(refresh=refresh)
        return df["Symbol"].dropna().astype(str).str.upper().unique().tolist()


if __name__ == "__main__":
    universe = StockUniverse()
    symbols = universe.get_symbols(refresh=True)
    print("NIFTY 100 stocks loaded:", len(symbols))
