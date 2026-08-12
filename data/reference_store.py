"""Daily pre-market reference data: PDC and previous-day direction."""
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

    @property
    def date_key(self):
        # Reference files must be keyed to the Indian trading date, not the
        # Streamlit server's UTC/system date.
        return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")

    @property
    def path(self):
        return self.folder / f"references_{self.date_key}.csv"

    @staticmethod
    def _ticker(symbol):
        return symbol if str(symbol).endswith(".NS") else f"{symbol}.NS"

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
        rows = []
        try:
            raw = yf.download(
                tickers=tickers,
                period="10d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker",
            )
            for symbol, ticker in zip(symbols, tickers):
                try:
                    data = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) and ticker in raw.columns.get_level_values(0) else raw
                    if data is None or data.empty:
                        continue
                    data = data.dropna(subset=["Open", "Close"])
                    if data.empty:
                        continue
                    dates = pd.to_datetime(data.index).date
                    # Ignore today's partial daily row. PDC is always the
                    # most recent completed Indian trading session.
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
                        "PreviousDayDirection": "BULLISH" if pdc > prev_open else "BEARISH" if pdc < prev_open else "NEUTRAL",
                    })
                except Exception as error:
                    print("Reference error", symbol, error)
        except Exception as error:
            print("Reference batch download failed:", error)

        result = pd.DataFrame(rows)
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
