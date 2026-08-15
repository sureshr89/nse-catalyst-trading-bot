"""Trade and signal journal for the NIFTY 500 paper strategy without sector analysis."""
import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import TRADE_LOG_FILE, SIGNAL_LOG_FILE
from papertrade.persistent_storage import restore, sync

INDIA_TZ = ZoneInfo("Asia/Kolkata")

class TradeJournal:
    TRADE_COLUMNS=["trade_id","symbol","stock","signal","buy_sell","entry_time","trigger_entry_time","market_entry_time","entry","stop_loss","target","quantity","exit_time","exit_price","exit_reason","risk","reward","rr","pnl","risk_per_share","actual_risk","position_value","open_cross_level","pdh","pdl","today_open","today_low","today_high","previous_day_close","gap","gap_percent","gap_type","market_direction","stock_direction","stock_today_direction","setup_type","trigger_candle_open","trigger_candle_close","trigger_close","pdh_pdl_reached","liquidity_qualified","nifty500_universe","signal_quality_score","why_this_trade","mae","mfe","status"]
    SIGNAL_COLUMNS=["timestamp","symbol","signal","market_direction","stock_direction","stock_today_direction","pdh","pdl","today_open","today_low","today_high","previous_day_close","gap","gap_percent","gap_type","entry","stop_loss","target","quantity","risk_reward","risk_per_share","actual_risk","position_value","open_cross_level","setup_type","trigger_candle_open","trigger_candle_close","trigger_close","pdh_pdl_reached","liquidity_qualified","nifty500_universe","approved","reason"]
    EXIT_FIELDS={"exit_time","exit_price","exit_reason","pnl","status","mae","mfe"}
    LEGACY_COLUMNS={"nifty100_direction","pdc","previous_day_direction","gap_direction","gap_failure","open_reclaim"}

    def __init__(self,trade_file=TRADE_LOG_FILE,signal_file=SIGNAL_LOG_FILE):
        self.trade_file=trade_file;self.signal_file=signal_file;self._prepare_files();restore(self.trade_file,self.trade_file.replace(os.sep,"/"));restore(self.signal_file,self.signal_file.replace(os.sep,"/"));self._prepare_files()

    def _prepare_files(self):
        for path,columns in ((self.trade_file,self.TRADE_COLUMNS),(self.signal_file,self.SIGNAL_COLUMNS)):
            directory=os.path.dirname(path)
            if directory:os.makedirs(directory,exist_ok=True)
            if not os.path.exists(path):self._write_header(path,columns);continue
            try:
                df=pd.read_csv(path)
                legacy=self.LEGACY_COLUMNS.intersection(set(df.columns))
                if legacy:df=df.drop(columns=list(legacy),errors="ignore")
                for column in columns:
                    if column not in df.columns:df[column]=""
                df=df.reindex(columns=columns)
                if path==self.signal_file:df=self._deduplicate_signal_history(df)
                df.to_csv(path,index=False)
            except (FileNotFoundError,pd.errors.EmptyDataError):self._write_header(path,columns)

    @staticmethod
    def _write_header(path,columns):
        with open(path,"w",newline="",encoding="utf-8") as file:csv.DictWriter(file,fieldnames=columns).writeheader()
    @staticmethod
    def _value(value):
        if value is None:return ""
        if hasattr(value,"isoformat"):
            try:return value.isoformat()
            except Exception:pass
        return value
    @staticmethod
    def _normalise(value):
        if value is None:return ""
        if isinstance(value,float):return f"{value:.8f}"
        text=str(value).strip()
        try:return f"{float(text):.8f}"
        except (TypeError,ValueError):return text.upper()
    @staticmethod
    def _journal_ist(value):
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if pd.isna(parsed):return pd.NaT
            if getattr(parsed,"tzinfo",None) is None:return parsed.tz_localize(INDIA_TZ)
            return parsed.tz_convert(INDIA_TZ)
        except Exception:return pd.NaT
    @classmethod
    def _series_dates_ist(cls,series):return series.map(cls._journal_ist)
    @staticmethod
    def _signal_date(signal):
        value=signal.get("timestamp") or signal.get("entry_time") or ""
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if pd.isna(parsed):return ""
            if getattr(parsed,"tzinfo",None) is None:return parsed.date().isoformat()
            return parsed.tz_convert(INDIA_TZ).date().isoformat()
        except Exception:return ""
    def _daily_setup_key(self,signal):return (self._signal_date(signal),self._normalise(signal.get("symbol","")),self._normalise(signal.get("signal","")),self._normalise(signal.get("setup_type","")))
    def _deduplicate_signal_history(self,df):
        if df.empty:return df
        keys=df.apply(self._daily_setup_key,axis=1);return df.loc[~keys.duplicated(keep="first")].reset_index(drop=True)
    def signal_exists(self,signal):
        try:df=pd.read_csv(self.signal_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return False
        if df.empty:return False
        return self._daily_setup_key(signal) in {self._daily_setup_key(row.to_dict()) for _,row in df.iterrows()}
    @staticmethod
    def _research_context(trade):
        score=0;reasons=[];side=str(trade.get("signal",trade.get("buy_sell",""))).upper();required="BULLISH" if side=="BUY" else "BEARISH" if side=="SELL" else ""
        if required and str(trade.get("market_direction","")).upper()==required:score+=30;reasons.append("NIFTY 500 aligned")
        if required and str(trade.get("stock_direction",trade.get("stock_today_direction","")).upper())==required:score+=30;reasons.append("Stock aligned")
        try:
            gap=abs(float(trade.get("gap_percent",0) or 0))
            if gap>0:score+=20;reasons.append(f"Gap {gap:.2f}%")
        except Exception:pass
        try:
            entry=pd.to_datetime(trade.get("entry_time"),errors="coerce")
            if not pd.isna(entry):
                if getattr(entry,"tzinfo",None) is not None:entry=entry.tz_convert(INDIA_TZ)
                minute=entry.hour*60+entry.minute
                if 585<=minute<=840:score+=10;reasons.append("09:45–14:00 entry window")
        except Exception:pass
        return score," • ".join(reasons) or "Recorded setup context only"
    def upsert_trade(self,trade):
        if not isinstance(trade,dict):return {"saved":False,"reason":"Trade must be a dictionary"}
        trade_id=str(trade.get("trade_id","")).strip()
        if not trade_id:return {"saved":False,"reason":"Missing trade_id"}
        trade=dict(trade);score,explanation=self._research_context(trade)
        if trade.get("signal_quality_score","") in (None,""):trade["signal_quality_score"]=score
        if not trade.get("why_this_trade"):trade["why_this_trade"]=explanation
        row={column:self._value(trade.get(column,"")) for column in self.TRADE_COLUMNS}
        try:df=pd.read_csv(self.trade_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):df=pd.DataFrame(columns=self.TRADE_COLUMNS)
        for column in self.TRADE_COLUMNS:
            if column not in df.columns:df[column]=""
        mask=df["trade_id"].astype(str).str.strip()==trade_id if not df.empty else pd.Series(dtype=bool)
        if not df.empty and bool(mask.any()):
            idx=df.index[mask][0]
            for column in self.TRADE_COLUMNS:
                if row[column]!="" or column in self.EXIT_FIELDS:df.at[idx,column]=row[column]
        else:df=pd.concat([df,pd.DataFrame([row])],ignore_index=True)
        df.reindex(columns=self.TRADE_COLUMNS).to_csv(self.trade_file,index=False);sync(self.trade_file,self.trade_file.replace(os.sep,"/"),f"Save paper trade {trade_id}");return {"saved":True,"trade_id":trade_id}
    def log_trade(self,trade):
        if not isinstance(trade,dict):return {"saved":False,"reason":"Trade must be a dictionary"}
        status=str(trade.get("status","")).strip().upper()
        if status not in {"OPEN","CLOSED"}:return {"saved":False,"reason":"Trade status must be OPEN or CLOSED"}
        return self.upsert_trade(trade)
    def log_signal(self,signal):
        if not isinstance(signal,dict) or not bool(signal.get("approved",False)):return {"saved":False,"reason":"Only approved signals are journaled"}
        if self.signal_exists(signal):return {"saved":False,"duplicate":True,"reason":"Duplicate daily setup"}
        row={column:self._value(signal.get(column,"")) for column in self.SIGNAL_COLUMNS}
        if not row["timestamp"]:row["timestamp"]=datetime.now(INDIA_TZ).isoformat()
        with open(self.signal_file,"a",newline="",encoding="utf-8") as file:csv.DictWriter(file,fieldnames=self.SIGNAL_COLUMNS).writerow(row)
        sync(self.signal_file,self.signal_file.replace(os.sep,"/"),"Save approved scanner signal");return {"saved":True,"duplicate":False}
    def get_trades(self):
        try:return pd.read_csv(self.trade_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return pd.DataFrame(columns=self.TRADE_COLUMNS)
    def get_signals(self):
        try:return pd.read_csv(self.signal_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return pd.DataFrame(columns=self.SIGNAL_COLUMNS)
    def summary(self):
        """Return today's journal statistics; analysis pages read the full CSV separately."""
        df=self.get_trades()
        empty={"total_trades":0,"winning_trades":0,"losing_trades":0,"breakeven_trades":0,"win_rate":0.0,"total_pnl":0.0,"average_pnl":0.0}
        if df.empty or "status" not in df.columns:return empty
        closed=df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
        if closed.empty:return empty
        if "exit_time" in closed.columns:
            dates=self._series_dates_ist(closed["exit_time"])
            closed=closed[dates.dt.date==datetime.now(INDIA_TZ).date()]
        if closed.empty:return empty
        pnl=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0.0);total=len(pnl);winning=int((pnl>0).sum());losing=int((pnl<0).sum());breakeven=int((pnl==0).sum())
        return {"total_trades":total,"winning_trades":winning,"losing_trades":losing,"breakeven_trades":breakeven,"win_rate":round(winning/total*100,2),"total_pnl":round(float(pnl.sum()),2),"average_pnl":round(float(pnl.mean()),2)}
