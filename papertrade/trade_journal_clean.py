"""Trade and signal journal for the clean NIFTY 500 S1-S5 paper strategy."""
import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import TRADE_LOG_FILE, SIGNAL_LOG_FILE, MAX_TRADES_PER_STRATEGY_PER_DAY, DAILY_MAX_LOSS_PER_STRATEGY
from papertrade.persistent_storage import restore, sync
from strategy.contracts import STRATEGY_VERSION, STRATEGY_RULES

INDIA_TZ=ZoneInfo("Asia/Kolkata")
STRATEGIES=tuple(STRATEGY_RULES.keys())
NEWS_COLUMNS=["news_sentiment","news_confidence","news_headline","news_reason","news_source","news_checked_at"]

class TradeJournal:
    """Durable CSV journal with idempotent trade updates and daily-safe analytics."""
    TRADE_COLUMNS=[
        "trade_id","candidate_id","symbol","stock","signal","buy_sell","entry_time","trigger_entry_time","market_entry_time",
        "entry","stop_loss","target","quantity","exit_time","exit_price","exit_reason","risk","reward","rr",
        "pnl","risk_per_share","actual_risk","position_value","open_cross_level","pdh","pdl","today_open",
        "today_low","today_high","previous_day_close","gap","gap_percent","gap_type","market_direction",
        "nifty500_change_pct","setup_type","entry_source","candidate_state","atr_pct","rvol","beta","traded_value","priority_rank",
        "pdh_pdl_reached","nifty500_universe",*NEWS_COLUMNS,"strategy_version","status"
    ]
    SIGNAL_COLUMNS=[
        "timestamp","candidate_id","symbol","signal","market_direction","nifty500_change_pct","pdh","pdl","today_open","today_low",
        "today_high","previous_day_close","gap","gap_percent","gap_type","entry","stop_loss","target","quantity",
        "risk_reward","risk_per_share","actual_risk","position_value","open_cross_level","setup_type","entry_source","candidate_state",
        "atr_pct","rvol","beta","traded_value","priority_rank","pdh_pdl_reached","nifty500_universe",*NEWS_COLUMNS,
        "strategy_version","approved","reason"
    ]
    EXIT_FIELDS={"exit_time","exit_price","exit_reason","pnl","status","mae","mfe"}

    def __init__(self, trade_file=TRADE_LOG_FILE, signal_file=SIGNAL_LOG_FILE):
        self.trade_file=trade_file;self.signal_file=signal_file;self._prepare_files();restore(self.trade_file,self.trade_file.replace(os.sep,"/"));restore(self.signal_file,self.signal_file.replace(os.sep,"/"));self._prepare_files()

    def _prepare_files(self):
        for path,columns in ((self.trade_file,self.TRADE_COLUMNS),(self.signal_file,self.SIGNAL_COLUMNS)):
            directory=os.path.dirname(path)
            if directory:os.makedirs(directory,exist_ok=True)
            if not os.path.exists(path):self._write_header(path,columns);continue
            try:
                df=pd.read_csv(path)
                for column in columns:
                    if column not in df.columns:df[column]=""
                ordered=columns+[c for c in df.columns if c not in columns]
                df=df.reindex(columns=ordered)
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

    def _daily_setup_key(self,signal):
        candidate_id=str(signal.get("candidate_id","")).strip().upper()
        if candidate_id:return (self._signal_date(signal),"CANDIDATE",candidate_id)
        trigger=signal.get("trigger_entry_time") or signal.get("entry_time") or signal.get("timestamp") or ""
        parsed=self._journal_ist(trigger);trigger_key=parsed.isoformat() if not pd.isna(parsed) else self._normalise(trigger)
        return (self._signal_date(signal),self._normalise(signal.get("symbol","")),self._normalise(signal.get("signal","")),self._normalise(signal.get("setup_type","")),trigger_key)

    def _deduplicate_signal_history(self,df):
        if df.empty:return df
        keys=df.apply(self._daily_setup_key,axis=1)
        return df.loc[~keys.duplicated(keep="first")].reset_index(drop=True)

    def signal_exists(self,signal):
        try:df=pd.read_csv(self.signal_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return False
        if df.empty:return False
        return self._daily_setup_key(signal) in {self._daily_setup_key(row.to_dict()) for _,row in df.iterrows()}

    @staticmethod
    def _strategy_name(value):
        value=str(value or "").strip().upper();return value if value in STRATEGIES else ""

    def _validate_strategy_fields(self,record):
        strategy=self._strategy_name(record.get("setup_type"))
        if not strategy:return None,"Missing or invalid setup_type; expected one of S1-S5"
        current_version=str(record.get("strategy_version") or STRATEGY_VERSION).strip()
        if current_version!=STRATEGY_VERSION:return None,f"Strategy version mismatch: {current_version} != {STRATEGY_VERSION}"
        signal=str(record.get("signal") or record.get("buy_sell") or "").strip().upper()
        if signal not in {"BUY","SELL"}:return None,"Signal must be BUY or SELL"
        normalised=dict(record);normalised["setup_type"]=strategy;normalised["strategy_version"]=STRATEGY_VERSION;normalised["signal"]=signal;normalised["buy_sell"]=signal
        return normalised,None

    def upsert_trade(self,trade):
        if not isinstance(trade,dict):return {"saved":False,"reason":"Trade must be a dictionary"}
        trade_id=str(trade.get("trade_id","")).strip()
        if not trade_id:return {"saved":False,"reason":"Missing trade_id"}
        normalized,reason=self._validate_strategy_fields(trade)
        if normalized is None:return {"saved":False,"reason":reason}
        status=str(normalized.get("status","OPEN")).strip().upper()
        if status not in {"OPEN","CLOSED"}:return {"saved":False,"reason":"Trade status must be OPEN or CLOSED"}
        row={column:self._value(normalized.get(column,"")) for column in self.TRADE_COLUMNS};row["strategy_version"]=STRATEGY_VERSION
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
        ordered=self.TRADE_COLUMNS+[c for c in df.columns if c not in self.TRADE_COLUMNS]
        df.reindex(columns=ordered).to_csv(self.trade_file,index=False)
        sync(self.trade_file,self.trade_file.replace(os.sep,"/"),f"Save paper trade {trade_id}")
        return {"saved":True,"trade_id":trade_id}

    def log_trade(self,trade):
        if not isinstance(trade,dict):return {"saved":False,"reason":"Trade must be a dictionary"}
        return self.upsert_trade(trade)

    def log_signal(self,signal):
        if not isinstance(signal,dict):return {"saved":False,"reason":"Signal must be a dictionary"}
        normalized,reason=self._validate_strategy_fields(signal)
        if normalized is None:return {"saved":False,"reason":reason}
        if self.signal_exists(normalized):return {"saved":False,"duplicate":True,"reason":"Duplicate setup"}
        row={column:self._value(normalized.get(column,"")) for column in self.SIGNAL_COLUMNS}
        if not row["timestamp"]:row["timestamp"]=datetime.now(INDIA_TZ).isoformat()
        row["strategy_version"]=STRATEGY_VERSION
        with open(self.signal_file,"a",newline="",encoding="utf-8") as file:csv.DictWriter(file,fieldnames=self.SIGNAL_COLUMNS).writerow(row)
        sync(self.signal_file,self.signal_file.replace(os.sep,"/"),"Save scanner signal decision")
        return {"saved":True,"duplicate":False}

    def get_trades(self):
        try:return pd.read_csv(self.trade_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return pd.DataFrame(columns=self.TRADE_COLUMNS)

    def get_signals(self):
        try:return pd.read_csv(self.signal_file)
        except (FileNotFoundError,pd.errors.EmptyDataError):return pd.DataFrame(columns=self.SIGNAL_COLUMNS)

    def summary(self):
        df=self.get_trades();empty={"total_trades":0,"winning_trades":0,"losing_trades":0,"breakeven_trades":0,"win_rate":0.0,"total_pnl":0.0,"average_pnl":0.0}
        if df.empty or "status" not in df.columns:return empty
        closed=df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
        if closed.empty:return empty
        if "exit_time" in closed.columns:
            dates=self._series_dates_ist(closed["exit_time"]);closed=closed.loc[dates.notna() & (dates.dt.date==datetime.now(INDIA_TZ).date())]
        if closed.empty:return empty
        pnl=pd.to_numeric(closed["pnl"],errors="coerce").dropna()
        if pnl.empty:return empty
        total=len(pnl);winning=int((pnl>0).sum());losing=int((pnl<0).sum());breakeven=int((pnl==0).sum())
        return {"total_trades":total,"winning_trades":winning,"losing_trades":losing,"breakeven_trades":breakeven,"win_rate":round(winning/total*100,2),"total_pnl":round(float(pnl.sum()),2),"average_pnl":round(float(pnl.mean()),2)}

    def daily_strategy_limits(self):
        """Return entry count and realised P&L by strategy for today's session."""
        out={s:{"trades":0,"closed_trades":0,"pnl":0.0,"trade_limit":int(MAX_TRADES_PER_STRATEGY_PER_DAY),"loss_limit":float(DAILY_MAX_LOSS_PER_STRATEGY)} for s in STRATEGIES}
        df=self.get_trades()
        if df.empty or "entry_time" not in df.columns:return out
        entry_dates=self._series_dates_ist(df["entry_time"]);session=df.loc[entry_dates.notna() & (entry_dates.dt.date==datetime.now(INDIA_TZ).date())].copy()
        for _,row in session.iterrows():
            strategy=self._strategy_name(row.get("setup_type"))
            if not strategy:continue
            out[strategy]["trades"]+=1
            if str(row.get("status","")).upper()=="CLOSED":
                out[strategy]["closed_trades"]+=1;pnl=pd.to_numeric(pd.Series([row.get("pnl",0)]),errors="coerce").iloc[0]
                if pd.notna(pnl):out[strategy]["pnl"]+=float(pnl)
        for strategy in STRATEGIES:out[strategy]["pnl"]=round(out[strategy]["pnl"],2)
        return out
