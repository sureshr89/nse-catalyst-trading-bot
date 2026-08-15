"""Core paper-trading orchestration for the NIFTY 500 open-reversal strategy."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import pandas as pd
from config.settings import PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MAX_OPEN_POSITIONS, DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES
from scanner.scanner_engine import ScannerEngine
from strategy.risk_engine import RiskEngine
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from papertrade.missed_capital_tracker import MissedCapitalTracker
INDIA_TZ=ZoneInfo("Asia/Kolkata")

class TradingBot:
    """Run one NIFTY 500 paper-trading session without live execution."""
    def __init__(self):
        if LIVE_TRADING: raise RuntimeError("LIVE_TRADING must be False. This application is paper trading only.")
        if not PAPER_TRADING: raise RuntimeError("PAPER_TRADING must be True.")
        self.scanner=ScannerEngine();self.risk_engine=RiskEngine();self.price_data=PriceData();self.paper_engine=PaperTradeEngine();self.journal=TradeJournal();self._restore_risk_counts_from_paper_state();self.missed_capital=MissedCapitalTracker(self.journal,self.price_data);self.running=True;self.processed_signals=set();self.daily_pnl=self._restore_daily_pnl();self.cooldown_until=self._restore_cooldown();self.square_off_done=False
    @staticmethod
    def _now():return datetime.now(INDIA_TZ)
    @staticmethod
    def _journal_ist(value):
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if pd.isna(parsed):return pd.NaT
            if getattr(parsed,"tzinfo",None) is None:return parsed.tz_localize(INDIA_TZ)
            return parsed.tz_convert(INDIA_TZ)
        except Exception:return pd.NaT
    def _journal_dates_ist(self,series):return series.map(self._journal_ist)
    def current_time(self):return self._now().strftime("%H:%M")
    def _restore_risk_counts_from_paper_state(self):
        """Reconcile today's persisted paper trades into RiskEngine after a crash/restart."""
        today=self._now().date()
        try:
            for trade in list(self.paper_engine.open_positions.values())+list(self.paper_engine.closed_positions):
                if not isinstance(trade,dict):continue
                entry_dt=self._journal_ist(trade.get("entry_time"))
                if pd.isna(entry_dt) or entry_dt.date()!=today:continue
                symbol=str(trade.get("symbol","")).strip().upper()
                if not symbol:continue
                if self.risk_engine.get_trade_count(symbol)<self.risk_engine.max_trades_per_stock:self.risk_engine.register_trade(symbol)
        except Exception as error:print("Paper-state risk-count recovery skipped:",error)
    def _today_closed_trades(self):
        """Return today's CLOSED trades from journal + persisted paper state, deduplicated by trade_id."""
        today=self._now().date();merged={}
        try:
            df=self.journal.get_trades()
            if not df.empty and "exit_time" in df.columns:
                exits=self._journal_dates_ist(df["exit_time"])
                status=df["status"].astype(str).str.upper() if "status" in df.columns else pd.Series("CLOSED",index=df.index)
                for idx,row in df[status.eq("CLOSED")].iterrows():
                    exit_dt=exits.loc[idx] if idx in exits.index else pd.NaT
                    if pd.notna(exit_dt) and exit_dt.date()==today:
                        trade=dict(row);trade_id=str(trade.get("trade_id","")).strip();key=trade_id or f"journal:{idx}";merged[key]=trade
        except Exception as error:print("Journal closed-trade recovery skipped:",error)
        try:
            for trade in self.paper_engine.closed_positions:
                if not isinstance(trade,dict) or str(trade.get("status","")).upper()!="CLOSED":continue
                exit_dt=self._journal_ist(trade.get("exit_time"))
                if pd.notna(exit_dt) and exit_dt.date()==today:
                    trade_id=str(trade.get("trade_id","")).strip();key=trade_id or f"paper:{trade.get('symbol','')}:{trade.get('exit_time','')}";merged[key]=dict(trade)
        except Exception as error:print("Paper-state closed-trade recovery skipped:",error)
        return list(merged.values())
    def _restore_daily_pnl(self):
        try:
            trades=self._today_closed_trades();return round(sum(float(pd.to_numeric(pd.Series([trade.get("pnl",0)]),errors="coerce").fillna(0).iloc[0]) for trade in trades),2)
        except Exception as error:print("Daily P&L restore skipped:",error);return 0.0
    def _restore_cooldown(self):
        try:
            stop_times=[]
            for trade in self._today_closed_trades():
                if str(trade.get("exit_reason","")).upper()=="STOP_LOSS":
                    exit_dt=self._journal_ist(trade.get("exit_time"))
                    if pd.notna(exit_dt):stop_times.append(exit_dt)
            if not stop_times:return None
            end=max(stop_times).to_pydatetime()+timedelta(minutes=COOLDOWN_MINUTES);now=self._now();return end.replace(tzinfo=None) if end>now.replace(tzinfo=None) else None
        except Exception:return None
    def signal_key(self,signal):return (str(signal.get("symbol","")).strip().upper(),str(signal.get("signal","")).strip().upper(),str(signal.get("trigger_entry_time",signal.get("entry_time",""))),str(signal.get("open_cross_level","")))
    def daily_limit_reached(self):return self.daily_pnl<=-float(DAILY_MAX_LOSS) or self.daily_pnl>=float(DAILY_PROFIT_TARGET)
    def cooldown_active(self):
        if self.cooldown_until is None:return False
        now=self._now().replace(tzinfo=None)
        if now>=self.cooldown_until:self.cooldown_until=None;return False
        return True
    def log_signal(self,signal,risk_result):
        row=dict(signal);row.update({"risk_per_share":risk_result.get("risk_per_share",""),"actual_risk":risk_result.get("actual_risk",""),"position_value":risk_result.get("position_value","")});row["timestamp"]=signal.get("entry_time") or self._now().isoformat();row["approved"]=bool(risk_result.get("approved",False));reasons=risk_result.get("reasons",[]);row["reason"]="; ".join(map(str,reasons)) if isinstance(reasons,list) else str(reasons)
        try:self.journal.log_signal(row)
        except Exception as error:print("Signal journal save failed:",error)
    def _attach_trade_context(self,position,signal):
        fields=("open_cross_level","pdh","pdl","today_open","today_low","today_high","market_direction","stock_direction","stock_today_direction","setup_type","trigger_candle_open","trigger_candle_close","trigger_close","pdh_pdl_reached","liquidity_qualified","nifty500_universe","risk_per_share","actual_risk","position_value","previous_day_close","gap","gap_percent","gap_type")
        for field in fields:
            if field in signal:position[field]=signal[field]
        return position
    def _rollback_registered_trade(self,symbol):
        try:
            count=self.risk_engine.get_trade_count(symbol)
            if count>0:self.risk_engine.trade_counts[symbol]=count-1
        except Exception as error:print("Risk trade-count rollback failed:",error)
    def _rollback_open_position(self,symbol):
        try:
            if self.paper_engine.has_open_position(symbol):
                position=self.paper_engine.open_positions.pop(symbol);position_value=float(position.get("position_value",float(position.get("entry",0) or 0)*int(float(position.get("quantity",0) or 0))));self.paper_engine.used_capital=round(max(0.0,self.paper_engine.used_capital-position_value),2);self.paper_engine.available_capital=round(self.paper_engine.total_capital-self.paper_engine.used_capital,2);self.paper_engine._save_state()
        except Exception as error:print(f"Paper position rollback failed for {symbol}: {type(error).__name__}: {error}")
    def _persist_closed_trade(self,trade):
        """Persist a CLOSED trade with short retries; journal writes upsert by trade_id."""
        if not isinstance(trade,dict) or not trade.get("trade_id"):return False
        for attempt in range(3):
            try:
                result=self.journal.log_trade(dict(trade))
                if result.get("saved",False):return True
            except Exception as error:
                if attempt==2:print(f"Closed trade journal save failed for {trade.get('symbol','')}: {type(error).__name__}: {error}")
            if attempt<2:time.sleep(0.5*(attempt+1))
        return False
    def _retry_closed_journal(self):
        """Reconcile persisted paper-engine CLOSED trades into the journal after transient failures."""
        all_saved=True
        for trade in list(self.paper_engine.closed_positions):
            if str(trade.get("exit_time","")).strip() and str(trade.get("status","")).upper()=="CLOSED":
                if not self._persist_closed_trade(trade):all_saved=False
        return all_saved
    def process_signal(self,signal):
        if not isinstance(signal,dict):return
        entry_time=signal.get("entry_time");parsed_entry=pd.to_datetime(entry_time,errors="coerce")
        if entry_time is None or pd.isna(parsed_entry):return
        if getattr(parsed_entry,"tzinfo",None) is None:parsed_entry=parsed_entry.tz_localize(INDIA_TZ)
        else:parsed_entry=parsed_entry.tz_convert(INDIA_TZ)
        if parsed_entry.date()!=self._now().date():return
        signal["trigger_entry_time"]=entry_time;key=self.signal_key(signal)
        if key in self.processed_signals:return
        symbol=str(signal.get("symbol","")).strip().upper()
        if not symbol:return
        if self.daily_limit_reached() or self.cooldown_active() or len(self.paper_engine.open_positions)>=MAX_OPEN_POSITIONS or self.paper_engine.has_open_position(symbol):return
        available_capital=float(self.paper_engine.available_capital);risk_result=self.risk_engine.approve_trade(signal, available_capital=available_capital);self.log_signal(signal,risk_result)
        if not risk_result.get("approved",False):self.processed_signals.add(key);return
        approved_trade=dict(signal);approved_trade.update(risk_result);approved_trade["approved"]=True
        try:result=self.paper_engine.open_trade(approved_trade)
        except Exception as error:self._rollback_registered_trade(symbol);print(f"Paper trade open failed for {symbol}; risk state rolled back: {type(error).__name__}: {error}");return
        if not result.get("opened",False):
            if result.get("reason","")=="Insufficient available capital":self.missed_capital.record(signal,risk_result,result["reason"])
            self._rollback_registered_trade(symbol);self.processed_signals.add(key);return
        position=self.paper_engine.open_positions.get(symbol)
        if position is None:self._rollback_registered_trade(symbol);print(f"Paper trade {symbol} reported opened but position state was missing");return
        self._attach_trade_context(position,approved_trade)
        try:
            journal_result=self.journal.log_trade(position.copy())
            if not journal_result.get("saved",False):self._rollback_open_position(symbol);self._rollback_registered_trade(symbol);print(f"Paper trade {symbol} rolled back because the OPEN trade journal could not be saved");return
        except Exception as error:self._rollback_open_position(symbol);self._rollback_registered_trade(symbol);print(f"Open trade journal save failed for {symbol}; paper position rolled back: {type(error).__name__}: {error}") ;return
        self.processed_signals.add(key)
    def _process_open_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            candle=self.latest_1m_candle(symbol)
            if candle is None:continue
            closed=self.paper_engine.process_candle(symbol,candle)
            if closed is not None:
                closed_pnl=float(pd.to_numeric(pd.Series([closed.get("pnl",0)]),errors="coerce").fillna(0).iloc[0]);self.daily_pnl=round(self.daily_pnl+closed_pnl,2);self._persist_closed_trade(closed)
                if str(closed.get("exit_reason","")).upper()=="STOP_LOSS":
                    exit_dt=self._journal_ist(closed.get("exit_time"));cooldown_base=exit_dt.to_pydatetime() if pd.notna(exit_dt) else self._now();self.cooldown_until=(cooldown_base+timedelta(minutes=COOLDOWN_MINUTES)).replace(tzinfo=None)
        self._retry_closed_journal();self.missed_capital.monitor()
    def _persist_master_data(self):
        try:
            from master_data import build_master_data;build_master_data()
        except Exception as error:print("Master data finalization skipped:",type(error).__name__,error)
    def _square_off_price(self,symbol,position):
        """Return a fresh exit price; never use an arbitrarily old scanner candle."""
        try:
            quote=self.price_data.get_latest_market_price(symbol)
            if quote and pd.to_numeric(pd.Series([quote.get("Close")]),errors="coerce").notna().iloc[0]:return float(quote.get("Close")), quote.get("Datetime") or self._now()
        except Exception as error:print(f"Latest quote unavailable for {symbol}: {type(error).__name__}: {error}")
        try:
            candle=self.latest_1m_candle(symbol)
            if candle is not None and pd.to_numeric(pd.Series([candle.get("Close")]),errors="coerce").notna().iloc[0]:return float(candle.get("Close")), candle.get("Datetime") or self._now()
        except Exception as error:print(f"Latest 1m fallback unavailable for {symbol}: {type(error).__name__}: {error}")
        try:
            candles=self.scanner.universe_market_data.get(symbol)
            if candles is not None and not candles.empty:
                row=candles.iloc[-1];close=pd.to_numeric(pd.Series([row.get("Close")]),errors="coerce").iloc[0];stamp=self._journal_ist(row.get("Datetime"))
                if pd.notna(close) and pd.notna(stamp):
                    age=(self._now()-stamp.to_pydatetime()).total_seconds()
                    if 0<=age<=120:return float(close),stamp.to_pydatetime()
                    print(f"Cached scanner price for {symbol} is stale ({age:.0f}s); square-off will retry")
        except Exception as error:print(f"Cached scanner price unavailable for {symbol}: {type(error).__name__}: {error}")
        return None,None
    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            position=self.paper_engine.open_positions.get(symbol,{});price,exit_time=self._square_off_price(symbol,position)
            if price is None:print(f"15:00 square-off price unavailable for {symbol}; position remains open until a valid market price is available");continue
            closed=self.paper_engine.close_position(symbol,price,exit_time,"SQUARE_OFF")
            if closed is not None:self.daily_pnl=round(self.daily_pnl+float(closed.get("pnl",0) or 0),2)
        journal_ok=self._retry_closed_journal();self._persist_master_data();self.square_off_done=(not bool(self.paper_engine.open_positions)) and journal_ok
    def scan_for_entries(self):
        now=self.current_time()
        if now<TRADING_START or now>LAST_ENTRY_TIME or self.daily_limit_reached() or self.cooldown_active() or len(self.paper_engine.open_positions)>=MAX_OPEN_POSITIONS:return
        for signal in self.scanner.scan() or []:
            if self.daily_limit_reached() or self.cooldown_active() or len(self.paper_engine.open_positions)>=MAX_OPEN_POSITIONS:break
            self.process_signal(signal)
    def latest_1m_candle(self,symbol):
        try:return self.price_data.get_latest_available_1m(symbol)
        except Exception as error:print(symbol,"1-minute data error:",error);return None
    def run_cycle(self):
        if self.current_time()>=SQUARE_OFF_TIME:
            if not self.square_off_done:self.square_off_all()
            return
        self.square_off_done=False;self._process_open_positions();self.scan_for_entries()
