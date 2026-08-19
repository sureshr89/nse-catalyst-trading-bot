"""Reliable NIFTY 500 universe loader with multiple remote and local fallbacks."""
from io import StringIO
from pathlib import Path
import time
import pandas as pd
import requests


class StockUniverse:
    MIN_EXPECTED_STOCKS = 450
    NSE_API = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"
    NIFTY_INDICES_CSV = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
    WIKI_URL = "https://en.wikipedia.org/wiki/NIFTY_500"

    def __init__(self):
        self.data_folder = Path("data")
        self.output_file = self.data_folder / "nifty500.csv"
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
            "Accept": "application/json,text/csv,text/html,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }

    def _clean(self, df):
        if df is None or df.empty:
            return None
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        symbol_col = next((c for c in df.columns if str(c).strip().lower() in {"symbol", "symbol name"}), None)
        if symbol_col is None:
            return None
        df["Symbol"] = (df[symbol_col].astype(str).str.strip().str.upper().str.replace(".NS", "", regex=False))
        df = df[df["Symbol"].ne("") & df["Symbol"].ne("NAN") & df["Symbol"].ne("NONE")].drop_duplicates("Symbol")
        industry_col = next((c for c in df.columns if str(c).strip().lower() in {"industry", "industry name"}), None)
        df["Industry"] = df[industry_col].astype(str).str.strip() if industry_col else "UNKNOWN"
        return df[["Symbol", "Industry"]].reset_index(drop=True)

    def _download_csv(self):
        try:
            r = requests.get(self.NIFTY_INDICES_CSV, headers=self.headers, timeout=15)
            if r.ok and r.text.strip():
                return self._clean(pd.read_csv(StringIO(r.text)))
        except Exception as error:
            print("NIFTY Indices universe download error:", error)
        return None

    def _download_nse(self):
        session = requests.Session()
        try:
            session.headers.update(self.headers)
            session.get("https://www.nseindia.com/", timeout=10)
            time.sleep(0.2)
            r = session.get(self.NSE_API, timeout=15)
            if not r.ok or not r.text.strip():
                return None
            payload = r.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            return self._clean(pd.DataFrame(rows)) if rows else None
        except Exception as error:
            print("NSE NIFTY 500 universe download error:", error)
        finally:
            session.close()
        return None

    def _download_wikipedia(self):
        """Last-resort constituent source for cloud environments blocking NSE."""
        try:
            tables = pd.read_html(self.WIKI_URL)
            for table in tables:
                cleaned = self._clean(table)
                if cleaned is not None and len(cleaned) >= self.MIN_EXPECTED_STOCKS:
                    return cleaned
        except Exception as error:
            print("Wikipedia NIFTY 500 universe fallback error:", error)
        return None

    def download(self):
        for loader in (self._download_csv, self._download_nse, self._download_wikipedia):
            df = loader()
            if df is not None and len(df) >= self.MIN_EXPECTED_STOCKS:
                df["Universe"] = "NIFTY500"
                return df
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
            cleaned = self._clean(df)
            if cleaned is None or len(cleaned) < self.MIN_EXPECTED_STOCKS:
                return None
            cleaned["Universe"] = "NIFTY500"
            return cleaned
        except Exception as error:
            print("Local universe read error:", error)
            return None

    def get_dataframe(self, refresh=True):
        local = self.load_local()
        if refresh:
            fresh = self.download()
            if fresh is not None:
                self.save(fresh)
                return fresh
        if local is not None:
            return local
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
