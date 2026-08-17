"""Daily PDH/PDL and previous-close reference data for the NIFTY 500 strategy."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import threading
import time
import pandas as pd
import yfinance as yf
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_REF_LOCK = threading.RLock()
_LAST_CALL = 0.0


class ReferenceStore:
    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.folder = Path("outputs") / "open_reversal_references"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.batch_size = 50
        self.max_workers = 2
        self.minimum_coverage = 0.60
        # A partial reference set is still usable. The scanner itself will show
        # the actual coverage instead of stopping the whole Strategy 2 worker.
        self.fallback_coverage = 0.01

    @property
    def date_key(self): return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
    @property
    def path(self): return self.folder / f"nifty500_open_reversal_{self.date_key}.csv"

    @staticmethod
    def _clean_symbol(symbol):
        return str(symbol).strip().upper().replace(".NS", "")

    @staticmethod
    def _ticker(symbol): return f"{ReferenceStore._clean_symbol(symbol)}.NS"

    def _coverage(self, df):
        if df is None or df.empty or self.universe.empty or "Symbol" not in df.columns: return 0.0
        universe = {self._clean_symbol(x) for x in self.universe["Symbol"]}
        found = {self._clean_symbol(x) for x in df["Symbol"]}
        return len(universe & found) / len(universe) if universe else 0.0

    def _coverage_ok(self, df, minimum=None):
        return self._coverage(df) >= (self.minimum_coverage if minimum is None else minimum)

    def _normalise_daily(self, data):
        if data is None or data.empty: return pd.DataFrame()
        frame = data.copy()
        if isinstance(frame.columns, pd.MultiIndex): frame.columns = [c[0] if isinstance(c, tuple) else c for c in frame.columns]
        if "Datetime" not in frame.columns: frame = frame.reset_index()
        rename = {}
        for column in frame.columns:
            low = str(column).strip().lower()
            if low in {"datetime", "date"}: rename[column] = "Datetime"
            elif low == "open": rename[column] = "Open"
            elif low == "high": rename[column] = "High"
            elif low == "low": rename[column] = "Low"
            elif low == "close": rename[column] = "Close"
            elif low == "volume": rename[column] = "Volume"
        frame = frame.rename(columns=rename)
        required = ["Datetime", "Open", "High", "Low", "Close"]
        if any(c not in frame.columns for c in required): return pd.DataFrame()
        dates = pd.to_datetime(frame["Datetime"], errors="coerce")
        try: dates = dates.dt.tz_localize(INDIA_TZ) if dates.dt.tz is None else dates.dt.tz_convert(INDIA_TZ)
        except Exception: return pd.DataFrame()
        frame["Datetime"] = dates
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in frame.columns: frame[c] = pd.to_numeric(frame[c], errors="coerce")
        return frame.dropna(subset=required).sort_values("Datetime").reset_index(drop=True)

    def _rows_from_daily_map(self, daily_map, symbols):
        today = datetime.now(INDIA_TZ).date(); rows = []
        # Accept both SYMBOL and SYMBOL.NS keys so the reference layer is not
        # coupled to the exact key convention of the market-data provider.
        normalised = {self._clean_symbol(k): v for k, v in (daily_map or {}).items()}
        for symbol in symbols:
            clean = self._clean_symbol(symbol)
            try:
                data = self._normalise_daily(normalised.get(clean))
                if data.empty: continue
                previous = data[data["Datetime"].dt.date < today]
                if previous.empty: continue
                current = data[data["Datetime"].dt.date == today]
                prev = previous.iloc[-1]
                pdc = float(prev["Close"]); volume = float(prev.get("Volume", 0) or 0)
                rows.append({"Symbol": clean, "PDH": round(float(prev["High"]),4), "PDL": round(float(prev["Low"]),4), "PreviousDayClose": round(pdc,4), "PreviousDayVolume": volume, "PreviousDayTurnover": round(pdc*volume,2), "TodayOpen": float(current.iloc[0]["Open"]) if not current.empty else None})
            except Exception: continue
        return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()

    def _download_batch(self, tickers):
        global _LAST_CALL
        with _REF_LOCK:
            wait = 0.25 - (time.monotonic() - _LAST_CALL)
            if wait > 0: time.sleep(wait)
            _LAST_CALL = time.monotonic()
        try:
            return yf.download(tickers=tickers, period="10d", interval="1d", auto_adjust=False, progress=False, threads=False, group_by="ticker", timeout=10)
        except Exception as error:
            print(f"Reference batch failed: {type(error).__name__}: {error}"); return pd.DataFrame()

    def _prepare_with_price_data(self, symbols):
        try: return self._rows_from_daily_map(PriceData().get_multi_daily(symbols, period="10d"), symbols)
        except Exception as error:
            print(f"Reference shared daily-data failed: {type(error).__name__}: {error}"); return pd.DataFrame()

    def _prepare_with_yfinance(self, symbols):
        clean_symbols = [self._clean_symbol(s) for s in symbols]; tickers = [self._ticker(s) for s in clean_symbols]; today = datetime.now(INDIA_TZ).date(); rows = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._download_batch, tickers[i:i+self.batch_size]): tickers[i:i+self.batch_size] for i in range(0,len(tickers),self.batch_size)}
            for future in as_completed(futures):
                batch = futures[future]
                try: raw = future.result()
                except Exception: continue
                if raw is None or raw.empty: continue
                for symbol, ticker in zip(clean_symbols, tickers):
                    if ticker not in batch: continue
                    try:
                        if isinstance(raw.columns, pd.MultiIndex):
                            level0=set(raw.columns.get_level_values(0)); level1=set(raw.columns.get_level_values(1)); data=raw[ticker] if ticker in level0 else raw.xs(ticker,axis=1,level=1) if ticker in level1 else None
                        else: data=raw if len(batch)==1 else None
                        data=self._normalise_daily(data)
                        if data.empty: continue
                        previous=data[data["Datetime"].dt.date<today]
                        if previous.empty: continue
                        current=data[data["Datetime"].dt.date==today]; prev=previous.iloc[-1]; pdc=float(prev["Close"]); volume=float(prev.get("Volume",0) or 0)
                        rows.append({"Symbol":symbol,"PDH":round(float(prev["High"]),4),"PDL":round(float(prev["Low"]),4),"PreviousDayClose":round(pdc,4),"PreviousDayVolume":volume,"PreviousDayTurnover":round(pdc*volume,2),"TodayOpen":float(current.iloc[0]["Open"]) if not current.empty else None})
                    except Exception: continue
        return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()

    def _cached_file_is_valid(self, saved):
        required={"Symbol","PDH","PDL","PreviousDayClose","PreviousDayVolume","PreviousDayTurnover","PreparedAtIST"}
        if not required.issubset(saved.columns) or not self._coverage_ok(saved,self.fallback_coverage): return False
        try:
            prepared=pd.to_datetime(saved["PreparedAtIST"],errors="coerce"); prepared=prepared.dt.tz_localize(INDIA_TZ) if prepared.dt.tz is None else prepared.dt.tz_convert(INDIA_TZ); return not prepared.dt.date.ne(datetime.now(INDIA_TZ).date()).any()
        except Exception: return False

    def _save_result(self, result):
        result=result.merge(self.universe[["Symbol","Industry"]],on="Symbol",how="left"); result["PreparedAtIST"]=datetime.now(INDIA_TZ).isoformat(timespec="seconds"); result["ReferenceCoverage"]=round(self._coverage(result)*100,1); result.to_csv(self.path,index=False)
        board=result.dropna(subset=["TodayOpen"]).copy()
        if not board.empty:
            board["Gap"]=board["TodayOpen"]-board["PreviousDayClose"]; board["GapPercent"]=board["Gap"]/board["PreviousDayClose"]*100
            board["GapType"]=board.apply(lambda r:"GAP_UP" if r["TodayOpen"]>r["PDH"] else "GAP_DOWN" if r["TodayOpen"]<r["PDL"] else "INSIDE_PDH_PDL",axis=1)
            board["GapFromPDH_PDL"]=board.apply(lambda r:r["TodayOpen"]-r["PDH"] if r["GapType"]=="GAP_UP" else r["TodayOpen"]-r["PDL"] if r["GapType"]=="GAP_DOWN" else 0.0,axis=1)
            board["GapPercentFromPDH_PDL"]=board["GapFromPDH_PDL"]/board["PDH"].where(board["GapType"]=="GAP_UP",board["PDL"])*100; board.to_csv(Path("outputs")/"gap_analysis.csv",index=False)
        return result

    def prepare(self):
        if self.path.exists():
            try:
                saved=pd.read_csv(self.path)
                if self._cached_file_is_valid(saved): return saved
            except Exception: pass
        symbols=self.universe["Symbol"].astype(str).str.upper().drop_duplicates().tolist()
        if not symbols: return pd.DataFrame()
        result=self._prepare_with_price_data(symbols); best=result
        if not self._coverage_ok(result):
            fallback=self._prepare_with_yfinance(symbols)
            if self._coverage(fallback)>self._coverage(best): best=fallback
        coverage=self._coverage(best)
        if best.empty or coverage<self.fallback_coverage: return pd.DataFrame()
        if coverage<self.minimum_coverage: print(f"Partial NIFTY 500 reference coverage: {coverage:.1%}; continuing with available symbols.")
        return self._save_result(best)

    def load(self): return self.prepare()
