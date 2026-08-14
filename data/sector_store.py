"""Sector classification for the active NIFTY 500 scanner universe."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

INDIA_TZ = ZoneInfo("Asia/Kolkata")
MIN_COVERAGE = 0.95
CACHE_MAX_AGE_DAYS = 7


class SectorStore:
    """Prepare sector buckets for NIFTY 500 and refresh them at most weekly."""

    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.path = Path("data") / "nifty500_sectors.csv"

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

    def _valid_cached(self, cached, minimum_rows):
        required = {"Symbol", "Sector", "SectorSource", "PreparedAtIST"}
        if not required.issubset(cached.columns) or len(cached) < minimum_rows:
            return False
        universe_symbols = set(self.universe["Symbol"].astype(str).str.upper())
        cached_symbols = set(cached["Symbol"].astype(str).str.upper())
        if not universe_symbols.issubset(cached_symbols):
            return False
        prepared = pd.to_datetime(cached["PreparedAtIST"], errors="coerce")
        if prepared.isna().all():
            return False
        latest = prepared.max()
        if latest.tzinfo is None:
            latest = latest.tz_localize(INDIA_TZ)
        else:
            latest = latest.tz_convert(INDIA_TZ)
        return datetime.now(INDIA_TZ) - latest.to_pydatetime() <= timedelta(days=CACHE_MAX_AGE_DAYS)

    def prepare(self, force=False):
        if self.universe.empty or "Symbol" not in self.universe.columns:
            return pd.DataFrame(columns=["Symbol", "Sector", "SectorSource", "PreparedAtIST"])

        minimum_rows = max(1, int(len(self.universe) * MIN_COVERAGE))
        if not force and self.path.exists():
            try:
                cached = pd.read_csv(self.path)
                if self._valid_cached(cached, minimum_rows):
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

        result["Sector"] = result["Symbol"].map(sectors).fillna(result["Industry"])
        result.loc[result["Sector"] == "", "Sector"] = "UNKNOWN"
        result["SectorSource"] = result["Symbol"].map(lambda symbol: "YAHOO_SECTOR" if sectors.get(symbol) else "NIFTY_INDUSTRY_FALLBACK")
        result["PreparedAtIST"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result = result[["Symbol", "Sector", "SectorSource", "PreparedAtIST"]].drop_duplicates("Symbol").reset_index(drop=True)

        if len(result) < minimum_rows:
            print(f"Sector mapping incomplete: {len(result)}/{len(self.universe)}")
            return pd.DataFrame(columns=["Symbol", "Sector", "SectorSource", "PreparedAtIST"])

        result.to_csv(self.path, index=False)
        return result

    def load(self):
        return self.prepare()
