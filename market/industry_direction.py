"""Industry and stock breadth engine for the Yahoo paper-trading bot.

Uses bounded Yahoo requests so one large 250-symbol request cannot block the
scanner indefinitely. Partial data is allowed; unavailable symbols are marked
NO_DATA and do not crash the scan.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
import yfinance as yf


class IndustryDirection:
    def __init__(self, universe_file="data/nifty_largemidcap_250.csv"):
        self.universe_file = Path(universe_file)
        self.stock_neutral_percent = 0.05
        self.industry_threshold = 60.0
        self.download_timeout = 10
        self.batch_size = 25
        self.max_workers = 8
        self.universe = pd.DataFrame()
        self.stock_results = pd.DataFrame()
        self.industry_results = pd.DataFrame()
        self._load_universe()

    def _load_universe(self):
        if not self.universe_file.exists():
            raise FileNotFoundError(f"Universe file not found: {self.universe_file}")
        df = pd.read_csv(self.universe_file)
        df.columns = [str(c).strip() for c in df.columns]
        missing = {"Symbol", "Industry"} - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")
        df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
        df["Industry"] = df["Industry"].fillna("UNKNOWN").astype(str).str.strip()
        self.universe = df.drop_duplicates("Symbol")[["Symbol", "Industry"]].reset_index(drop=True)

    def yahoo_symbol(self, symbol):
        symbol = str(symbol).strip().upper()
        return symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    def _clean_stock(self, data):
        if data is None or data.empty:
            return pd.DataFrame()
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                return pd.DataFrame()
        df = df.reset_index()
        dt_col = next((c for c in df.columns if str(c).lower() in {"datetime", "date"}), None)
        if dt_col is None:
            return pd.DataFrame()
        df = df.rename(columns={dt_col: "Datetime"})
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
        df = df.dropna(subset=["Datetime"])
        for col in ["Open", "High", "Low", "Close"]:
            if col not in df.columns:
                return pd.DataFrame()
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["Open", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    def _download_one(self, symbol):
        ticker = self.yahoo_symbol(symbol)
        try:
            data = yf.download(tickers=ticker, period="1d", interval="5m", auto_adjust=False,
                               progress=False, threads=False, prepost=False, timeout=self.download_timeout)
            return symbol, self._clean_stock(data)
        except Exception as error:
            print(f"Yahoo industry data failed {symbol}: {type(error).__name__}: {error}")
            return symbol, pd.DataFrame()

    def download_market_data(self):
        symbols = self.universe["Symbol"].tolist()
        results = {}
        print(f"Downloading 5-minute breadth data for {len(symbols)} stocks in batches of {self.batch_size}...")
        for start in range(0, len(symbols), self.batch_size):
            batch = symbols[start:start + self.batch_size]
            print(f"Yahoo batch {start + 1}-{start + len(batch)} / {len(symbols)}")
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = [pool.submit(self._download_one, symbol) for symbol in batch]
                for future in as_completed(futures):
                    symbol, data = future.result()
                    results[symbol] = data
        return results

    def _extract_stock_data(self, data, symbol):
        if isinstance(data, dict):
            return data.get(symbol, pd.DataFrame())
        return self._clean_stock(data)

    def classify_stock(self, data, symbol, industry):
        stock = self._extract_stock_data(data, symbol)
        if stock.empty:
            return {"Symbol": symbol, "Industry": industry, "DayOpen": None, "LastPrice": None, "ChangePercent": None, "Direction": "NO_DATA"}
        day_open = float(stock.iloc[0]["Open"])
        last_price = float(stock.iloc[-1]["Close"])
        change_percent = 0.0 if day_open == 0 else ((last_price - day_open) / day_open) * 100
        direction = "BULLISH" if change_percent > self.stock_neutral_percent else "BEARISH" if change_percent < -self.stock_neutral_percent else "NEUTRAL"
        return {"Symbol": symbol, "Industry": industry, "DayOpen": round(day_open, 2), "LastPrice": round(last_price, 2), "ChangePercent": round(change_percent, 3), "Direction": direction}

    def analyze_stocks(self, data):
        self.stock_results = pd.DataFrame([
            self.classify_stock(data, row["Symbol"], row["Industry"])
            for _, row in self.universe.iterrows()
        ])
        return self.stock_results

    def calculate_industries(self, stock_results):
        results = []
        for industry in sorted(self.universe["Industry"].unique().tolist()):
            group = stock_results[stock_results["Industry"] == industry]
            valid = group[group["Direction"] != "NO_DATA"]
            total = len(group)
            valid_count = len(valid)
            bullish = int((valid["Direction"] == "BULLISH").sum())
            bearish = int((valid["Direction"] == "BEARISH").sum())
            neutral = int((valid["Direction"] == "NEUTRAL").sum())
            no_data = total - valid_count
            bp = bullish / valid_count * 100 if valid_count else 0.0
            sp = bearish / valid_count * 100 if valid_count else 0.0
            np = neutral / valid_count * 100 if valid_count else 0.0
            if not valid_count:
                direction = "NO_DATA"
            elif bp >= self.industry_threshold:
                direction = "BULLISH"
            elif sp >= self.industry_threshold:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            results.append({"Industry": industry, "Total": total, "Valid": valid_count,
                            "Bullish": bullish, "Bearish": bearish, "Neutral": neutral,
                            "NoData": no_data, "BullishPercent": round(bp, 1),
                            "BearishPercent": round(sp, 1), "NeutralPercent": round(np, 1),
                            "Direction": direction})
        self.industry_results = pd.DataFrame(results)
        return self.industry_results

    def analyze(self):
        data = self.download_market_data()
        if not data:
            return pd.DataFrame(), pd.DataFrame()
        return self.analyze_stocks(data), self.calculate_industries(self.stock_results)

    def get_industry_direction(self, industry):
        if self.industry_results.empty:
            return "UNKNOWN"
        match = self.industry_results[self.industry_results["Industry"] == industry]
        return "UNKNOWN" if match.empty else str(match.iloc[0]["Direction"])

    def get_stock_direction(self, symbol):
        if self.stock_results.empty:
            return "UNKNOWN"
        symbol = str(symbol).strip().upper()
        match = self.stock_results[self.stock_results["Symbol"] == symbol]
        return "UNKNOWN" if match.empty else str(match.iloc[0]["Direction"])


if __name__ == "__main__":
    engine = IndustryDirection()
    stocks, industries = engine.analyze()
    print("Stocks analyzed:", len(stocks))
    print("Industries analyzed:", len(industries))
    if not stocks.empty:
        print("Stocks without data:", int((stocks["Direction"] == "NO_DATA").sum()))
    print("INDUSTRY DIRECTION ENGINE TEST COMPLETE")
