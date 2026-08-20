from pathlib import Path
import pandas as pd

class PriceData:
    def __init__(self):
        self._live_price_cache = {}
        self._live_price_cache_at = {}

    def get_latest_live_price(self, symbol):
        from market import dhan_data
        symbol = str(symbol).upper().strip()
        if not dhan_data.configured():
            return {"Symbol": symbol, "Close": None, "price_source": "UNAVAILABLE"}
        mapping = dhan_data.map_nifty500([symbol], force=False)
        quote = dhan_data.market_quote(mapping)
        if quote is None or quote.empty:
            return {"Symbol": symbol, "Close": None, "price_source": "UNAVAILABLE"}
        row = quote.iloc[0]
        close = pd.to_numeric(row.get("LTP"), errors="coerce")
        return {
            "Symbol": symbol,
            "Close": float(close) if pd.notna(close) else None,
            "Open": pd.to_numeric(row.get("TodayOpen"), errors="coerce"),
            "High": pd.to_numeric(row.get("TodayHigh"), errors="coerce"),
            "Low": pd.to_numeric(row.get("TodayLow"), errors="coerce"),
            "PreviousClose": pd.to_numeric(row.get("PreviousClose"), errors="coerce"),
            "NetChange": pd.to_numeric(row.get("NetChange"), errors="coerce"),
            "price_source": "DHAN_OHLC",
        }
