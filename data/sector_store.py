"""Cached sector grouping for the NIFTY 250 scanner universe."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

INDIA_TZ = ZoneInfo("Asia/Kolkata")
MIN_COVERAGE = 0.95


class SectorStore:
    """Prepare sector buckets once per IST date for the active scanner universe."""

    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.path = Path("data") / "nifty250_sectors.csv"

    @staticmethod
    def _yahoo_sector(symbol):
        try:
            info = yf.Ticker(f"{symbol}.NS").info
            sector = str(info.get("sector", "")).strip()
            return sector if sector else None
        except Exception:
            return None

    @staticmethod
    def _today_key():
        return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")

    def prepare(self, force=False):
        if self.universe.empty or "Symbol" not in self.universe.columns:
            return pd.DataFrame(columns=["Symbol", "Sector", "SectorSource", "PreparedAtIST"])

        today = self._today_key()
        required = {"Symbol", "Sector", "SectorSource", "PreparedAtIST"}
        minimum_rows = max(1, int(len(self.universe) * MIN_COVERAGE))

        if not force and self.path.exists():
            try:
                cached = pd.read_csv(self.path)
                prepared = pd.to_datetime(cached.get("PreparedAtIST"), errors="coerce")
                cache_is_today = bool(
                    not prepared.empty
                    and prepared.notna().all()
                    and prepared.dt.strftime("%Y-%m-%d").eq(today).all()
                )
                symbols_match = set(cached.get("Symbol", pd.Series(dtype=str)).astype(str).str.upper()) >= set(self.universe["Symbol"].astype(str).str.upper())
                if required.issubset(cached.columns) and cache_is_today and len(cached) >= minimum_rows and symbols_match:
                    return cached
            except Exception:
                pass

        result = self.universe[[c for c in ["Symbol", "Industry"] if c in self.universe.columns]].copy()
        if "Industry" not in result.columns:
            result["Industry"] = "UNKNOWN"
        result["Symbol"] = result["Symbol"].astype(str).str.upper().str.strip()
        result["Industry"] = result["Industry"].fillna("UNKNOWN").astype(str).str.strip()
        result.loc[result["Industry"] == "", "Industry"] = "UNKNOWN"

        sectors = {}
        symbols = result["Symbol"].drop_duplicates().tolist()
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self._yahoo_sector, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    sectors[symbol] = future.result()
                except Exception:
                    sectors[symbol] = None

        result["Sector"] = result["Symbol"].map(sectors)
        result["Sector"] = result["Sector"].fillna(result["Industry"])
        result.loc[result["Sector"] == "", "Sector"] = "UNKNOWN"
        result["SectorSource"] = result["Symbol"].map(
            lambda symbol: "YAHOO_SECTOR" if sectors.get(symbol) else "NIFTY_INDUSTRY_FALLBACK"
        )
        result["PreparedAtIST"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result = result[["Symbol", "Sector", "SectorSource", "PreparedAtIST"]].drop_duplicates("Symbol").reset_index(drop=True)

        if len(result) < minimum_rows:
            print(f"Sector mapping incomplete: {len(result)}/{len(self.universe)}. No cache written.")
            return pd.DataFrame(columns=["Symbol", "Sector", "SectorSource", "PreparedAtIST"])

        result.to_csv(self.path, index=False)
        return result

    def load(self):
        return self.prepare()
