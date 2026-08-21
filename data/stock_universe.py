"""Strict NIFTY 500 universe loader with official-source validation."""
from io import StringIO
from pathlib import Path
import time
import pandas as pd
import requests


class StockUniverse:
    """Load and validate the canonical NIFTY 500 universe.

    The live strategy requires exactly 500 unique constituents.  A local,
    previously validated file is therefore preferred and is only refreshed
    when explicitly requested or when no valid local universe exists.
    """

    REQUIRED_STOCKS = 500
    MIN_EXPECTED_STOCKS = 500
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

    @staticmethod
    def _normalise_text(value):
        text = str(value).strip()
        if text.upper() in {"", "NAN", "NONE", "<NA>", "NULL"}:
            return ""
        return text

    def _clean(self, df):
        if df is None or df.empty:
            return None
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        symbol_col = next(
            (
                c
                for c in df.columns
                if str(c).strip().lower()
                in {"symbol", "symbol name", "tradingsymbol", "trading symbol"}
            ),
            None,
        )
        if symbol_col is None:
            return None

        df["Symbol"] = (
            df[symbol_col]
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace(".NS", "", regex=False)
        )
        df = df[
            ~df["Symbol"].isin({"", "NAN", "NONE", "<NA>", "NULL"})
        ].drop_duplicates("Symbol")

        # Prefer the actual sector field.  Do not silently reinterpret an
        # industry classification as a sector; that can corrupt sector-majority
        # market alignment used by the strategy.
        sector_col = next(
            (
                c
                for c in df.columns
                if str(c).strip().lower()
                in {
                    "sector",
                    "sector name",
                    "macro economic sector",
                    "macro-economic sector",
                }
            ),
            None,
        )
        industry_col = next(
            (
                c
                for c in df.columns
                if str(c).strip().lower() in {"industry", "industry name"}
            ),
            None,
        )
        if sector_col is None:
            return None

        df["Sector"] = df[sector_col].map(self._normalise_text)
        df["Industry"] = (
            df[industry_col].map(self._normalise_text)
            if industry_col
            else df["Sector"]
        )
        df = df[df["Sector"].ne("")].copy()
        return df[["Symbol", "Industry", "Sector"]].reset_index(drop=True)

    def _download_csv(self):
        try:
            r = requests.get(self.NIFTY_INDICES_CSV, headers=self.headers, timeout=15)
            if r.ok and r.text.strip():
                x = self._clean(pd.read_csv(StringIO(r.text)))
                if x is not None and len(x) == self.REQUIRED_STOCKS:
                    return x
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
            x = self._clean(pd.DataFrame(rows)) if rows else None
            return x if x is not None and len(x) == self.REQUIRED_STOCKS else None
        except Exception as error:
            print("NSE NIFTY 500 universe download error:", error)
        finally:
            session.close()
        return None

    def _download_wikipedia(self):
        # Emergency fallback only.  It still must contain exactly 500 unique
        # constituents and a real sector field after normalisation.
        try:
            tables = pd.read_html(self.WIKI_URL)
            for table in tables:
                x = self._clean(table)
                if x is not None and len(x) == self.REQUIRED_STOCKS:
                    return x
        except Exception as error:
            print("Wikipedia NIFTY 500 universe fallback error:", error)
        return None

    def download(self):
        for loader in (self._download_csv, self._download_nse, self._download_wikipedia):
            df = loader()
            if df is not None and len(df) == self.REQUIRED_STOCKS:
                df["Universe"] = "NIFTY500"
                return df
        return None

    def save(self, df):
        if df is None or df.empty or len(df) != self.REQUIRED_STOCKS:
            return False
        if df["Symbol"].astype(str).str.upper().nunique() != self.REQUIRED_STOCKS:
            return False
        if df["Sector"].astype(str).str.strip().isin({"", "UNKNOWN", "NAN", "NONE"}).any():
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
            raw = pd.read_csv(self.output_file)
            cleaned = self._clean(raw)
            if cleaned is None or len(cleaned) != self.REQUIRED_STOCKS:
                return None
            if cleaned["Symbol"].nunique() != self.REQUIRED_STOCKS:
                return None
            if cleaned["Sector"].astype(str).str.strip().isin({"", "UNKNOWN", "NAN", "NONE"}).any():
                return None
            cleaned["Universe"] = "NIFTY500"
            return cleaned
        except Exception as error:
            print("Local universe read error:", error)
            return None

    def get_dataframe(self, refresh=False):
        """Return the validated local universe unless refresh is explicitly requested."""
        local = self.load_local()
        if local is not None and not refresh:
            return local

        fresh = self.download()
        if fresh is not None and self.save(fresh):
            return fresh

        # Never replace a valid local universe with an incomplete/unknown set
        # just because a network refresh failed.
        if local is not None:
            return local
        return pd.DataFrame(columns=["Symbol", "Industry", "Sector", "Universe"])

    def get_symbols(self, refresh=False):
        return (
            self.get_dataframe(refresh=refresh)["Symbol"]
            .dropna()
            .astype(str)
            .str.upper()
            .unique()
            .tolist()
        )
