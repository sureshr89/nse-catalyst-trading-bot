"""Daily PDH/PDL and previous-close reference data for the NIFTY 500 strategy."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

INDIA_TZ=ZoneInfo("Asia/Kolkata")
class ReferenceStore:
    def __init__(self,universe_df):
        self.universe=universe_df.copy();self.folder=Path("outputs")/"open_reversal_references";self.folder.mkdir(parents=True,exist_ok=True);self.batch_size=25;self.max_workers=4;self.minimum_coverage=0.60
    @property
    def date_key(self):return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
    @property
    def path(self):return self.folder/f"nifty500_open_reversal_{self.date_key}.csv"
    @staticmethod
    def _ticker(symbol):
        symbol=str(symbol).strip().upper();return symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    def _download_batch(self,tickers):
        try:return yf.download(tickers=tickers,period="10d",interval="1d",auto_adjust=False,progress=False,threads=False,group_by="ticker",timeout=10)
        except Exception:return pd.DataFrame()
    def _coverage_ok(self,df):
        if df is None or df.empty or self.universe.empty:return False
        required=max(1,int(len(self.universe)*self.minimum_coverage));u=set(self.universe["Symbol"].astype(str).str.upper());s=set(df["Symbol"].astype(str).str.upper()) if "Symbol" in df.columns else set();return len(u&s)>=required
    def _cached_file_is_valid(self,saved):
        required={"Symbol","PDH","PDL","PreviousDayClose","PreviousDayVolume","PreviousDayTurnover","PreparedAtIST"}
        if not required.issubset(saved.columns) or not self._coverage_ok(saved):return False
        try:
            p=pd.to_datetime(saved["PreparedAtIST"],errors="coerce");p=p.dt.tz_localize(INDIA_TZ) if p.dt.tz is None else p.dt.tz_convert(INDIA_TZ);return not p.dt.date.ne(datetime.now(INDIA_TZ).date()).any()
        except Exception:return False
    def prepare(self):
        if self.path.exists():
            try:
                saved=pd.read_csv(self.path)
                if self._cached_file_is_valid(saved):return saved
            except Exception:pass
        symbols=self.universe["Symbol"].astype(str).str.upper().tolist();tickers=[self._ticker(s) for s in symbols];today=datetime.now(INDIA_TZ).date();rows=[]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures={executor.submit(self._download_batch,tickers[i:i+self.batch_size]):tickers[i:i+self.batch_size] for i in range(0,len(tickers),self.batch_size)}
            for future in as_completed(futures):
                batch=futures[future]
                try:raw=future.result()
                except Exception:continue
                if raw is None or raw.empty:continue
                for symbol,ticker in zip(symbols,tickers):
                    if ticker not in batch:continue
                    try:
                        if isinstance(raw.columns,pd.MultiIndex):
                            l0=set(raw.columns.get_level_values(0));l1=set(raw.columns.get_level_values(1));data=raw[ticker] if ticker in l0 else raw.xs(ticker,axis=1,level=1) if ticker in l1 else None
                        else:data=raw if len(batch)==1 else None
                        if data is None or data.empty or any(c not in data.columns for c in ["Open","High","Low","Close"]):continue
                        data=data.dropna(subset=["Open","High","Low","Close"]);dates=pd.to_datetime(data.index,errors="coerce")
                        if getattr(dates,"tz",None) is not None:dates=dates.tz_convert(INDIA_TZ)
                        previous=data[[d.date()<today for d in dates]]
                        if previous.empty:continue
                        current=data[[d.date()==today for d in dates]];prev=previous.iloc[-1];pdc=float(prev["Close"]);today_open=float(current.iloc[0]["Open"]) if not current.empty else None;volume=float(prev.get("Volume",0) or 0)
                        rows.append({"Symbol":symbol,"PDH":round(float(prev["High"]),4),"PDL":round(float(prev["Low"]),4),"PreviousDayClose":round(pdc,4),"PreviousDayVolume":volume,"PreviousDayTurnover":round(pdc*volume,2),"TodayOpen":today_open})
                    except Exception:continue
        result=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        if result.empty or not self._coverage_ok(result):return pd.DataFrame()
        result=result.merge(self.universe[["Symbol","Industry"]],on="Symbol",how="left");result["PreparedAtIST"]=datetime.now(INDIA_TZ).isoformat(timespec="seconds");result.to_csv(self.path,index=False)
        board=result.dropna(subset=["TodayOpen"]).copy()
        board["Gap"]=board["TodayOpen"]-board["PreviousDayClose"];board["GapPercent"]=board["Gap"]/board["PreviousDayClose"]*100
        board["GapType"]=board.apply(lambda r:"GAP_UP" if r["TodayOpen"]>r["PDH"] else "GAP_DOWN" if r["TodayOpen"]<r["PDL"] else "INSIDE_PDH_PDL",axis=1)
        board["GapFromPDH_PDL"]=board.apply(lambda r:r["TodayOpen"]-r["PDH"] if r["GapType"]=="GAP_UP" else r["TodayOpen"]-r["PDL"] if r["GapType"]=="GAP_DOWN" else 0.0,axis=1)
        board["GapPercentFromPDH_PDL"]=board["GapFromPDH_PDL"]/board["PDH"].where(board["GapType"]=="GAP_UP",board["PDL"])*100
        board.to_csv(Path("outputs")/"gap_analysis.csv",index=False)
        return result
    def load(self):return self.prepare()
