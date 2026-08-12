"""Cached stock-to-sector mapping for the price-action sector filter."""
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf


class SectorStore:
    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.path = Path("data") / "nifty100_sectors.csv"

    def prepare(self):
        existing = self.load()
        mapping = {}
        if not existing.empty:
            mapping = dict(zip(existing["Symbol"], existing["Sector"]))

        for symbol, fallback in self.universe[["Symbol", "Industry"]].itertuples(index=False):
            symbol = str(symbol).upper()
            if mapping.get(symbol) and mapping[symbol] != "UNKNOWN":
                continue
            sector = None
            try:
                info = yf.Ticker(f"{symbol}.NS").info
                sector = info.get("sector") or info.get("sectorDisp")
            except Exception:
                sector = None
            mapping[symbol] = str(sector).strip() if sector else str(fallback or "UNKNOWN").strip()

        result = pd.DataFrame([{"Symbol": s, "Sector": mapping.get(s, "UNKNOWN")} for s in self.universe["Symbol"]])
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
