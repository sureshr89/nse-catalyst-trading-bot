"""Daily PDH/PDL and previous-close reference data for the NIFTY 500 strategy."""

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
        self.folder = Path("outputs") / "open_reversal_references"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.batch_size = 25
        self.max_workers = 4
        self.minimum_coverage = 0.95

    @property
    def date_key(self): return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
    @property
    def path(self): return self.folder / f"nifty500_open_reversal_{self.date_key}.csv"

    @staticmethod
    def _ticker(symbol):
        symbol = str(symbol).strip().upper()
        return symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    def _download_batch(self, tickers):
        try:
            return yf.download(tickers=tickers, period="10d", interval="1d", auto_adjust=False, progress=False, threads=False, group_by="ticker", timeout=10)
        except Exception as error:
            print(f"Reference batch download failed ({len(tickers)}):", error)
            return pd.DataFrame()

    def _coverage_ok(self, df):
        if df is None or df.empty or self.universe.empty: return False
        required = max(1, int(len(self.universe) * self.minimum_coverage))
        universe_symbols=set(self.universe["Symbol"].astype(str).str.upper())
        saved_symbols=set(df["Symbol"].astype(str).str.upper()) if "Symbol" in df.columns else set()
        return len(saved_symbols & universe_symbols) >= required

    def _cached_file_is_valid(self, saved):
        """Accept today's cache only when it was prepared for today's IST session and covers this universe."""
        required={"Symbol","PDH","PDL","PreviousDayClose","PreviousDayVolume","PreviousDayTurnover","PreparedAtIST"}
        if not required.issubset(saved.columns) or not self._coverage_ok(saved): return False
        try:
            prepared=pd.to_datetime(saved["PreparedAtIST"],errors="coerce")
            if prepared.isna().all(): return False
            prepared_ist=prepared.dt.tz_localize(INDIA_TZ) if prepared.dt.tz is None else prepared.dt.tz_convert(INDIA_TZ)
            if prepared_ist.dt.date.ne(datetime.now(INDIA_TZ).date()).any(): return False
        except Exception:
            return False
        return True

    def prepare(self):
        if self.path.exists():
            try:
                saved=pd.read_csv(self.path)
                if self._cached_file_is_valid(saved): return saved
                print("Today's saved NIFTY 500 references failed freshness/coverage validation; rebuilding.")
            except Exception as error:
                print("Saved NIFTY 500 references could not be loaded:", error)

        symbols=self.universe["Symbol"].astype(str).str.upper().tolist()
        tickers=[self._ticker(s) for s in symbols]
        today=datetime.now(INDIA_TZ).date()
        batches=[tickers[i:i+self.batch_size] for i in range(0,len(tickers),self.batch_size)]
        rows=[]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map={executor.submit(self._download_batch,batch):batch for batch in batches}
            for future in as_completed(future_map):
                batch=future_map[future]
                try: raw=future.result()
                except Exception as error:
                    print("Reference batch worker failed:", error); continue
                if raw is None or raw.empty: continue
                for symbol,ticker in zip(symbols,tickers):
                    if ticker not in batch: continue
                    try:
                        if isinstance(raw.columns,pd.MultiIndex):
                            level0=set(raw.columns.get_level_values(0));level1=set(raw.columns.get_level_values(1))
                            if ticker in level0:data=raw[ticker]
                            elif ticker in level1:data=raw.xs(ticker,axis=1,level=1)
                            else:continue
                        else:
                            if len(batch)!=1:continue
                            data=raw
                        if data is None or data.empty or any(c not in data.columns for c in ["Open","High","Low","Close"]): continue
                        data=data.dropna(subset=["Open","High","Low","Close"])
                        if data.empty:continue
                        index_dates=pd.to_datetime(data.index,errors="coerce")
                        if getattr(index_dates,"tz",None) is not None:index_dates=index_dates.tz_convert(INDIA_TZ)
                        completed=data[[d < today for d in index_dates.date]]
                        if completed.empty:continue
                        prev=completed.iloc[-1]
                        close=float(prev["Close"]);volume=float(prev.get("Volume",0) or 0)
                        rows.append({"Symbol":symbol,"PDH":round(float(prev["High"]),4),"PDL":round(float(prev["Low"]),4),"PreviousDayClose":round(close,4),"PreviousDayVolume":volume,"PreviousDayTurnover":round(close*volume,2)})
                    except Exception as error:print("Reference error",symbol,error)

        result=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        if result.empty or not self._coverage_ok(result):
            print("NIFTY 500 reference coverage incomplete:",len(result) if not result.empty else 0,"of",len(self.universe));return pd.DataFrame()
        result=result.merge(self.universe[["Symbol","Industry"]],on="Symbol",how="left")
        result["PreparedAtIST"]=datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result.to_csv(self.path,index=False)
        return result

    def load(self): return self.prepare()
