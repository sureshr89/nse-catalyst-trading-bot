"""NIFTY 100 price-action direction engine."""
import pandas as pd
import yfinance as yf


class MarketDirection:
    def __init__(self):
        self.market_ticker = "^CNX100"
        self.download_timeout = 10

    def _clean_data(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        data = df.copy()
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
        data = data.reset_index()
        dt = next((c for c in data.columns if str(c).lower() in {"datetime", "date"}), None)
        if dt is None:
            return pd.DataFrame()
        data = data.rename(columns={dt: "Datetime"})
        data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
        for c in ["Open", "High", "Low", "Close"]:
            if c not in data.columns:
                return pd.DataFrame()
            data[c] = pd.to_numeric(data[c], errors="coerce")
        return data.dropna(subset=["Datetime", "Open", "High", "Low", "Close"]).sort_values("Datetime").reset_index(drop=True)

    def get_market_data(self):
        try:
            return self._clean_data(yf.download(
                tickers=self.market_ticker, period="1d", interval="1m", auto_adjust=False,
                progress=False, threads=False, prepost=False, timeout=self.download_timeout,
            ))
        except Exception as error:
            print("Nifty 100 data download failed:", error)
            return pd.DataFrame()

    def calculate_direction(self, df):
        if df is None or df.empty:
            return {"direction": "UNKNOWN", "day_open": None, "current_price": None, "change": None, "change_percent": None}
        completed = df.iloc[:-1] if len(df) > 1 else df
        day_open = float(completed.iloc[0]["Open"])
        current_price = float(completed.iloc[-1]["Close"])
        change = current_price - day_open
        pct = 0.0 if day_open == 0 else change / day_open * 100
        return {"direction": "BULLISH" if change > 0 else "BEARISH" if change < 0 else "NEUTRAL",
                "day_open": round(day_open, 2), "current_price": round(current_price, 2),
                "change": round(change, 2), "change_percent": round(pct, 3)}

    def analyze(self):
        return self.calculate_direction(self.get_market_data())

    def buy_allowed(self):
        return self.analyze()["direction"] == "BULLISH"

    def sell_allowed(self):
        return self.analyze()["direction"] == "BEARISH"
