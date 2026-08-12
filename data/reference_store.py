"""Daily pre-market reference data: PDC and previous-day direction."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


INDIA_TZ = ZoneInfo("Asia/Kolkata")


class ReferenceStore:
    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.folder = Path("outputs") / "references"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.batch_size = 25
        self.max_workers = 4

    @property
    def date_key(self):
        return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")

    @property
    def path(self):
        return self.folder / f"references_{self.date_key}.csv"

    @staticmethod
    def _ticker(symbol):
        return symbol if str(symbol).endswith(".NS") else f"{symbol}.NS"

    def _download_batch(self, tickers):
        try:
            return yf.download(
                tickers=tickers,
                period="10d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                group_by="ticker",
                timeout=10,
            )
        except Exception as error:
            print(f"Reference batch download failed ({len(tickers)}):", error)
            return pd.DataFrame()

    def prepare(self):
        if self.path.exists():
            try:
                saved = pd.read_csv(self.path)
                if len(saved) >= max(1, int(len(self.universe) * 0.8)):
                    return saved
            except Exception:
                pass

        symbols = self.universe["Symbol"].astype(str).str.upper().tolist()
        tickers = [self._ticker(s) for s in symbols]
        today = datetime.now(INDIA_TZ).date()
        batches = [tickers[i:i + self.batch_size] for i in range(0, len(tickers), self.batch_size)]
        rows = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self._download_batch, batch): batch for batch in batches}
            for future in as_completed(future_map):
                batch = future_map[future]
                try:
                    raw = future.result()
                except Exception as error:
                    print("Reference batch worker failed:", error)
                    continue
                if raw is None or raw.empty:
                    continue

                for symbol, ticker in zip(symbols, tickers):
                    if ticker not in batch:
                        continue
                    try:
                        if isinstance(raw.columns, pd.MultiIndex):
                            level0 = set(raw.columns.get_level_values(0))
                            level1 = set(raw.columns.get_level_values(1))
                            if ticker in level0:
                                data = raw[ticker]
                            elif ticker in level1:
                                data = raw.xs(ticker, axis=1, level=1)
                            else:
                                continue
                        else:
                            if len(batch) != 1:
                                continue
                            data = raw

                        if data is None or data.empty or "Open" not in data.columns or "Close" not in data.columns:
                            continue
                        data = data.dropna(subset=["Open", "Close"])
                        if data.empty:
                            continue
                        dates = pd.to_datetime(data.index, errors="coerce").date
                        completed = data[[d < today for d in dates]]
                        if completed.empty:
                            continue
                        prev = completed.iloc[-1]
                        pdc = float(prev["Close"])
                        prev_open = float(prev["Open"])
                        rows.append({
                            "Symbol": symbol,
                            "PDC": round(pdc, 4),
                            "PreviousDayOpen": round(prev_open, 4),
                            "PreviousDayDirection": (
                                "BULLISH" if pdc > prev_open else
                                "BEARISH" if pdc < prev_open else "NEUTRAL"
                            ),
                        })
                    except Exception as error:
                        print("Reference error", symbol, error)

        result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        if result.empty:
            return result
        result = result.merge(self.universe[["Symbol", "Industry"]], on="Symbol", how="left")
        result = result.rename(columns={"Industry": "SectorFallback"})
        result["PreparedAtIST"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result.to_csv(self.path, index=False)
        return result

    def load(self):
        if not self.path.exists():
            return self.prepare()
        try:
            return pd.read_csv(self.path)
        except Exception:
            return self.prepare()
