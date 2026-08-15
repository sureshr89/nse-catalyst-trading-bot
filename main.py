"""Core paper-trading orchestration for the NIFTY 500 open-reversal strategy."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
        self.scanner=ScannerEngine();self.risk_engine=RiskEngine();self.price_data=PriceData();self.paper_engine=PaperTradeEngine();self.journal=TradeJournal();self.missed_capital=MissedCapitalTracker(self.journal,self.price_data);self.running=True;self.processed_signals=set();self.daily_pnl=self._restore_daily_pnl();self.cooldown_until=self._restore_cooldown();self.square_off_done=False
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
    def _restore_daily_pnl(self):
        try:
            df=self.journal.get_trades()
            if df.empty or "pnl" not in df.columns or "exit_time" not in df.columns:return 0.0
            exits=self._journal_dates_ist(df["exit_time"]);mask=exits.dt.date==self._now().date()
            if "status" in df.columns:mask &= df["status"].astype(str).str.upper().eq("CLOSED")
            return round(float(pd.to_numeric(df["pnl"],errors="coerce").fillna(0.0)[mask].sum()),2)
        except Exception as error:print("Daily P&L restore skipped:",error);return 0.0
    def _restore_cooldown(self):
        try:
            df=self.journal.get_trades()
            if df.empty or "exit_time" not in df.columns or "exit_reason" not in df.columns:return None
            status=df["status"].astype(str).str.upper() if "status" in df.columns else pd.Series("",index=df.index);closed=df[status.eq("CLOSED")].copy();closed=closed[closed["exit_reason"].astype(str).str.upper().eq("STOP_LOSS")]
            if closed.empty:return None
            times=self._journal_dates_ist(closed["exit_time"]);times=times[times.dt.date==self._now().date()].dropna()
            if times.empty:return None
            end=times.max().to_pydatetime()+timedelta(minutes=COOLDOWN_MINUTES);return end.replace(tzinfo=None) if end>self._now().replace(tzinfo=None) else None
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
        self.processed_signals.add(key);position=self.paper_engine.open_positions.get(symbol)
        if position is None:self._rollback_registered_trade(symbol);print(f"Paper trade {symbol} reported opened but position state was missing");return
        self._attach_trade_context(position,approved_trade)
        try:self.journal.log_trade(position.copy())
        except Exception as error:print(f"Open trade journal save failed for {symbol}: {type(error).__name__}: {error}")
    def _process_open_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            candle=self.latest_1m_candle(symbol)
            if candle is None:continue
            closed=self.paper_engine.process_candle(symbol,candle)
            if closed is not None:
                closed_pnl=float(pd.to_numeric(pd.Series([closed.get("pnl",0)]),errors="coerce").fillna(0).iloc[0]);self.daily_pnl=round(self.daily_pnl+closed_pnl,2)
                try:self.journal.log_trade(closed)
                except Exception as error:print(f"Closed trade journal save failed for {symbol}: {type(error).__name__}: {error}")
                if str(closed.get("exit_reason","")).upper()=="STOP_LOSS":self.cooldown_until=self._now().replace(tzinfo=None)+timedelta(minutes=COOLDOWN_MINUTES)
        self.missed_capital.monitor()
    def _persist_master_data(self):
        try:
            from master_data import build_master_data;build_master_data()
        except Exception as error:print("Master data finalization skipped:",type(error).__name__,error)
    def _square_off_price(self,symbol,position):
        """Return the freshest available exit price, with deterministic data fallbacks for the 15:00 paper square-off."""
        try:
            quote=self.price_data.get_latest_market_price(symbol)
            if quote and pd.to_numeric(pd.Series([quote.get("Close")]),errors="coerce").notna().iloc[0]:
                return float(quote.get("Close")), quote.get("Datetime") or self._now()
        except Exception as error:print(f"Latest quote unavailable for {symbol}: {type(error).__name__}: {error}")
        try:
            candle=self.latest_1m_candle(symbol)
            if candle is not None and pd.to_numeric(pd.Series([candle.get("Close")]),errors="coerce").notna().iloc[0]:
                return float(candle.get("Close")), candle.get("Datetime") or self._now()
        except Exception as error:print(f"Latest 1m fallback unavailable for {symbol}: {type(error).__name__}: {error}")
        try:
            candles=self.scanner.universe_market_data.get(symbol)
            if candles is not None and not candles.empty:
                row=candles.iloc[-1]
                close=pd.to_numeric(pd.Series([row.get("Close")]),errors="coerce").iloc[0]
                if pd.notna(close):return float(close),row.get("Datetime") or self._now()
        except Exception as error:print(f"Cached scanner price unavailable for {symbol}: {type(error).__name__}: {error}")
        return None,None
    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            position=self.paper_engine.open_positions.get(symbol,{})
            price,exit_time=self._square_off_price(symbol,position)
            if price is None:
                print(f"15:00 square-off price unavailable for {symbol}; position remains open until a valid market price is available")
                continue
            closed=self.paper_engine.close_position(symbol,price,exit_time,"SQUARE_OFF")
            if closed is not None:
                self.daily_pnl=round(self.daily_pnl+float(closed.get("pnl",0) or 0),2)
                try:self.journal.log_trade(closed)
                except Exception as error:print(f"Square-off journal save failed for {symbol}: {type(error).__name__}: {error}")
        self._persist_master_data();self.square_off_done=not bool(self.paper_engine.open_positions)
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
