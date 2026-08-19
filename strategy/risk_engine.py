"""Risk and position sizing gate for the five NIFTY 500 paper strategies."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import (
    TOTAL_CAPITAL, ALLOCATED_CAPITAL_PER_TRADE, MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK, MAX_TRADES_PER_STOCK, MAX_TRADES_PER_STRATEGY_PER_DAY,
    DAILY_MAX_LOSS_PER_STRATEGY, MIN_RR_RATIO, TRADE_LOG_FILE,
)

INDIA_TZ = ZoneInfo("Asia/Kolkata")

class RiskEngine:
    """Final safety gate. Quantity is derived from the actual entry-to-SL distance."""
    def __init__(self):
        self.total_capital = float(TOTAL_CAPITAL)
        self.allocated_capital_per_trade = float(ALLOCATED_CAPITAL_PER_TRADE)
        self.max_risk_per_trade = float(MAX_RISK_PER_TRADE)
        self.min_required_risk = float(MIN_REQUIRED_RISK)
        self.max_trades_per_stock = int(MAX_TRADES_PER_STOCK)
        self.max_trades_per_strategy = int(MAX_TRADES_PER_STRATEGY_PER_DAY)
        self.daily_max_loss_per_strategy = float(DAILY_MAX_LOSS_PER_STRATEGY)
        self.trade_counts = {}
        self.restore_today_trade_counts()

    @staticmethod
    def _number(value):
        try:
            n = float(value)
            return n if n == n else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _today_ist(): return datetime.now(INDIA_TZ).date()

    @staticmethod
    def _entry_date_ist(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed): return None
            if getattr(parsed, "tzinfo", None) is None: parsed = parsed.tz_localize(INDIA_TZ)
            else: parsed = parsed.tz_convert(INDIA_TZ)
            return parsed.date()
        except Exception: return None

    @staticmethod
    def _strategy_key(value):
        text = str(value or "").strip().upper()
        if text.startswith("STRATEGY_"): return "S" + text.split("_")[-1]
        if text in {"OPEN_RETURN", "S1"}: return "S1"
        if text in {"S2", "S3", "S4", "S5"}: return text
        return text or "UNKNOWN"

    def restore_today_trade_counts(self):
        self.trade_counts = {}
        path = Path(TRADE_LOG_FILE)
        if not path.exists(): return
        try: df = pd.read_csv(path)
        except Exception: return
        if df.empty or "entry_time" not in df.columns: return
        today = self._today_ist(); seen = set()
        for row in df.to_dict("records"):
            if self._entry_date_ist(row.get("entry_time")) != today: continue
            if str(row.get("status", "")).upper().startswith("MISSED_CAPITAL"): continue
            strategy = self._strategy_key(row.get("strategy")); symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol: continue
            key = (strategy, str(row.get("trade_id", "")), symbol, str(row.get("entry_time", "")), str(row.get("entry", "")))
            if key in seen: continue
            seen.add(key)
            self.trade_counts[(strategy, symbol)] = self.trade_counts.get((strategy, symbol), 0) + 1

    def get_trade_count(self, symbol, strategy=None):
        symbol = str(symbol).strip().upper()
        if strategy is not None: return self.trade_counts.get((self._strategy_key(strategy), symbol), 0)
        return sum(v for (s, sym), v in self.trade_counts.items() if sym == symbol)

    def get_strategy_trade_count(self, strategy):
        key = self._strategy_key(strategy)
        return sum(v for (s, _), v in self.trade_counts.items() if s == key)

    def register_trade(self, symbol, strategy=None):
        key = (self._strategy_key(strategy), str(symbol).strip().upper())
        self.trade_counts[key] = self.trade_counts.get(key, 0) + 1
        return self.trade_counts[key]

    def _strategy_daily_state(self, strategy):
        """Return today's realized P&L and open worst-case risk for one strategy."""
        key = self._strategy_key(strategy); realized = 0.0; open_risk = 0.0
        path = Path(TRADE_LOG_FILE)
        if path.exists():
            try:
                df = pd.read_csv(path)
                if not df.empty:
                    df["strategy_key"] = df.get("strategy", "").map(self._strategy_key)
                    mask = df["strategy_key"].eq(key)
                    if "status" in df.columns and "exit_time" in df.columns and "pnl" in df.columns:
                        closed = df[mask & df["status"].astype(str).str.upper().eq("CLOSED")]
                        if not closed.empty:
                            dates = closed["exit_time"].map(self._entry_date_ist)
                            realized = float(pd.to_numeric(closed.loc[dates.eq(self._today_ist()), "pnl"], errors="coerce").fillna(0).sum())
            except Exception: pass
        state_path = Path("outputs") / "paper_engine_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8")); positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
                for p in positions.values() if isinstance(positions, dict) else []:
                    if not isinstance(p, dict) or self._strategy_key(p.get("strategy")) != key: continue
                    entry=self._number(p.get("entry")); stop=self._number(p.get("stop_loss")); qty=self._number(p.get("quantity"))
                    if entry is not None and stop is not None and qty and qty > 0: open_risk += abs(entry-stop)*qty
            except Exception: pass
        return round(realized, 2), round(open_risk, 2)

    def validate(self, trade, check_trade_count=True, available_capital=None):
        if not isinstance(trade, dict): return {"approved":False,"reasons":["Trade must be a dictionary"]}
        symbol=str(trade.get("symbol","")).strip().upper(); signal=str(trade.get("signal","")).strip().upper(); strategy=self._strategy_key(trade.get("strategy"))
        entry=self._number(trade.get("entry")); stop=self._number(trade.get("stop_loss")); target=self._number(trade.get("target")); reasons=[]
        available=self.total_capital if available_capital is None else (self._number(available_capital) or 0.0)
        capital=min(available,self.allocated_capital_per_trade)
        if not symbol: reasons.append("Missing symbol")
        if signal not in {"BUY","SELL"}: reasons.append("Signal must be BUY or SELL")
        if entry is None or entry<=0: reasons.append("Invalid entry price")
        if stop is None or stop<=0: reasons.append("Invalid stop loss")
        if target is None or target<=0: reasons.append("Invalid target")
        if entry is not None and stop is not None:
            if signal=="BUY" and stop>=entry: reasons.append("BUY stop loss must be below entry")
            if signal=="SELL" and stop<=entry: reasons.append("SELL stop loss must be above entry")
        if entry is not None and target is not None:
            if signal=="BUY" and target<=entry: reasons.append("BUY target must be above entry")
            if signal=="SELL" and target>=entry: reasons.append("SELL target must be below entry")
        if reasons: return {"approved":False,"symbol":symbol,"signal":signal,"strategy":strategy,"reasons":reasons}
        risk_per_share=abs(entry-stop); risk_qty=int(self.max_risk_per_trade//risk_per_share); capital_qty=int(capital//entry); quantity=min(risk_qty,capital_qty)
        if quantity<=0: return {"approved":False,"symbol":symbol,"signal":signal,"strategy":strategy,"reasons":["No quantity fits the Rs 2.5 lakh capital allocation"]}
        actual_risk=round(risk_per_share*quantity,2); position_value=round(entry*quantity,2); reward_per_share=(target-entry) if signal=="BUY" else (entry-target); reward=round(reward_per_share*quantity,2); rr=reward/actual_risk if actual_risk>0 else 0
        if rr<float(MIN_RR_RATIO): reasons.append(f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}")
        if actual_risk<float(self.min_required_risk): reasons.append(f"Actual risk Rs {actual_risk:.2f} is below minimum Rs {self.min_required_risk:.2f}")
        if actual_risk>self.max_risk_per_trade: reasons.append(f"Actual risk Rs {actual_risk:.2f} exceeds maximum Rs {self.max_risk_per_trade:.2f}")
        if position_value>capital: reasons.append(f"Position value Rs {position_value:.2f} exceeds Rs {capital:.2f} per-trade allocation")
        if check_trade_count:
            if self.get_strategy_trade_count(strategy)>=self.max_trades_per_strategy: reasons.append(f"{strategy} reached its daily maximum of {self.max_trades_per_strategy} trades")
            if self.get_trade_count(symbol,strategy)>=self.max_trades_per_stock: reasons.append(f"{symbol} already reached maximum trades per stock ({self.max_trades_per_stock})")
        realized,open_risk=self._strategy_daily_state(strategy)
        if realized-open_risk-actual_risk < -self.daily_max_loss_per_strategy:
            reasons.append(f"{strategy} daily loss limit: realized Rs {realized:.2f} + open risk Rs {open_risk:.2f} + new risk Rs {actual_risk:.2f} would exceed Rs {self.daily_max_loss_per_strategy:.2f}")
        return {"approved":not reasons,"symbol":symbol,"signal":signal,"strategy":strategy,"entry":round(entry,4),"stop_loss":round(stop,4),"target":round(target,4),"quantity":int(quantity),"risk_per_share":round(risk_per_share,4),"actual_risk":actual_risk,"reward":reward,"rr":round(rr,4),"min_rr_ratio":float(MIN_RR_RATIO),"min_required_risk":self.min_required_risk,"max_risk":self.max_risk_per_trade,"capital":capital,"position_value":position_value,"reasons":reasons}

    def approve_trade(self, trade, available_capital=None):
        result=self.validate(trade,check_trade_count=True,available_capital=available_capital)
        if not result.get("approved"): return result
        self.register_trade(result["symbol"],result.get("strategy")); result["trade_count"]=self.get_trade_count(result["symbol"],result.get("strategy")); result["strategy_trade_count"]=self.get_strategy_trade_count(result.get("strategy")); return result

    def calculate_position_size(self, entry, stop_loss, available_capital=None):
        entry=self._number(entry); stop_loss=self._number(stop_loss)
        if entry is None or stop_loss is None or entry<=0 or entry==stop_loss:return 0
        risk_per_share=abs(entry-stop_loss); risk_qty=int(self.max_risk_per_trade//risk_per_share); capital=self.allocated_capital_per_trade if available_capital is None else min(float(available_capital),self.allocated_capital_per_trade)
        return max(0,min(risk_qty,int(capital//entry)))
