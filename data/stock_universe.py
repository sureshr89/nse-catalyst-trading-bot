"""NIFTY 500 scanner universe with resilient local and NSE fallbacks."""
from io import StringIO
from pathlib import Path
import json

import pandas as pd
import requests


class StockUniverse:
    MIN_EXPECTED_STOCKS = 450

    def __init__(self):
        self.urls = {
            "NIFTY500": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
            "NSE_API": "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500",
        }
        self.data_folder = Path("data")
        self.output_file = self.data_folder / "nifty500.csv"
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/json,text/csv,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }

    def _download_niftyindices(self):
        try:
            session = requests.Session()
            session.headers.update(self.headers)
            session.get("https://www.niftyindices.com/", timeout=10)
            response = session.get(self.urls["NIFTY500"], timeout=15)
            if response.status_code == 200 and response.text.strip():
                return pd.read_csv(StringIO(response.text))
        except Exception as error:
            print("NIFTY Indices universe download error:", error)
        return None

    def _download_nse_api(self):
        """Get the live NIFTY 500 constituent list from NSE as a fallback.

        NSE's index endpoint returns the constituent rows in `data`; the first
        index summary row is excluded. This is used only for universe membership,
        not for strategy prices.
        """
        try:
            session = requests.Session()
            session.headers.update(self.headers)
            landing = session.get("https://www.nseindia.com/", timeout=10)
            if landing.status_code >= 400:
                return None
            response = session.get(self.urls["NSE_API"], timeout=15)
            if response.status_code != 200 or not response.text.strip():
                return None
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list) or not rows:
                return None
            frame = pd.DataFrame(rows)
            if "symbol" not in frame.columns:
                return None
            frame = frame.rename(columns={"symbol": "Symbol"})
            keep = [c for c in ["Symbol", "industryInfo"] if c in frame.columns]
            frame = frame[keep].copy()
            if "industryInfo" in frame.columns:
                frame = frame.rename(columns={"industryInfo": "Industry"})
            return frame
        except Exception as error:
            print("NSE API universe download error:", error)
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
        # NSE can return an index summary row; keep only real symbols.
        df = df[df[symbol_col].ne("") & ~df[symbol_col].isin({"NIFTY 500", "NIFTY500"})].drop_duplicates(symbol_col)
        if symbol_col != "Symbol":
            df = df.rename(columns={symbol_col: "Symbol"})
        if "Industry" not in df.columns:
            df["Industry"] = "UNKNOWN"
        df["Industry"] = df["Industry"].fillna("UNKNOWN").astype(str)
        return df.reset_index(drop=True)

    def download(self):
        for downloader in (self._download_niftyindices, self._download_nse_api):
            try:
                df = self._clean(downloader())
                if df is not None and not df.empty and len(df) >= self.MIN_EXPECTED_STOCKS:
                    df["Universe"] = "NIFTY500"
                    return df
            except Exception as error:
                print("Universe fallback failed:", error)
        return None

    def save(self, df):
        if df is None or df.empty or len(df) < self.MIN_EXPECTED_STOCKS:
            return False
        try:
            df.to_csv(self.output_file, index=False)
            return True
        except Exception as error:
            print("Universe save error:", error)
            return False

    def load_local(self):
        if not self.output_file.exists():
            return None
        try:
            df = pd.read_csv(self.output_file)
            df = self._clean(df)
            return df if df is not None and len(df) >= self.MIN_EXPECTED_STOCKS else None
        except Exception as error:
            print("Local universe read error:", error)
            return None

    def get_dataframe(self, refresh=True):
        # Always prefer a fresh official list, but never allow a temporary remote
        # failure to turn the deployed scanner into an empty NIFTY 500 universe.
        local = self.load_local()
        if refresh:
            fresh = self.download()
            if fresh is not None:
                self.save(fresh)
                return fresh
        if local is not None:
            return local
        # If no local cache exists (common on a fresh Streamlit container), make
        # one last live attempt instead of returning an empty universe.
        fresh = self.download()
        if fresh is not None:
            self.save(fresh)
            return fresh
        return pd.DataFrame(columns=["Symbol", "Industry", "Universe"])

    def get_symbols(self, refresh=True):
        df = self.get_dataframe(refresh=refresh)
        return df["Symbol"].dropna().astype(str).str.upper().unique().tolist()


if __name__ == "__main__":
    symbols = StockUniverse().get_symbols(refresh=True)
    print("NIFTY 500 stocks loaded:", len(symbols))
