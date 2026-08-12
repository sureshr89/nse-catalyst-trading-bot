"""Cached sector grouping for the Nifty 100 price-action filter.

The official Nifty constituent CSV exposes an Industry grouping. This file
uses that published grouping as the stable sector bucket for the scanner so
sector alignment does not require 100 extra network calls during market hours.
"""
from datetime import datetime
from pathlib import Path
import pandas as pd


class SectorStore:
    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.path = Path("data") / "nifty100_sectors.csv"

    def prepare(self):
        result = self.universe[["Symbol", "Industry"]].copy()
        result["Symbol"] = result["Symbol"].astype(str).str.upper().str.strip()
        result["Sector"] = result["Industry"].fillna("UNKNOWN").astype(str).str.strip()
        result.loc[result["Sector"] == "", "Sector"] = "UNKNOWN"
        result = result[["Symbol", "Sector"]].drop_duplicates("Symbol").reset_index(drop=True)
        result["PreparedAtIST"] = datetime.now().isoformat(timespec="seconds")
        result.to_csv(self.path, index=False)
        return result

    def load(self):
        if not self.path.exists():
            return pd.DataFrame(columns=["Symbol", "Sector"])
        try:
            df = pd.read_csv(self.path)
            if "Symbol" not in df.columns or "Sector" not in df.columns:
                return pd.DataFrame(columns=["Symbol", "Sector"])
            return df
        except Exception:
            return pd.DataFrame(columns=["Symbol", "Sector"])
