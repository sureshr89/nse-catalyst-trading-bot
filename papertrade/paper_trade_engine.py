"""Persistent paper-trade execution engine for the NIFTY 500 strategy."""
import json, os, re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MARKET_CLOSE, TOTAL_CAPITAL, MAX_OPEN_POSITIONS, MIN_REQUIRED_RISK, MAX_RISK_PER_TRADE, MIN_RR_RATIO, TRADE_LOG_FILE
from market.price_data import PriceData
from papertrade.persistent_storage import restore_json, sync_json
INDIA_TZ=ZoneInfo("Asia/Kolkata")
STATE_VERSION=5
class PaperTradeEngine:
    """Simulated execution engine. Live trading is deliberately prohibited."""
    def __init__(self):
        self.paper_trading=bool(PAPER_TRADING); self.live_trading=bool(LIVE_TRADING); self.trading_start=TRADING_START; self.last_entry_time=LAST_ENTRY_TIME; self.square_off_time=SQUARE_OFF_TIME; self.market_close=MARKET_CLOSE; self.open_positions={}; self.closed_positions=[]; self.trade_counter=0; self.total_capital=float(TOTAL_CAPITAL); self.available_capital=float(TOTAL_CAPITAL); self.used_capital=0.0; self.price_data=PriceData(); self._restore_state()
    def _state_path(self): return os.path.join("outputs","paper_engine_state.json")
    @staticmethod
    def _number(value):
        try:
            n=float(value); return n if n==n else None
        except (TypeError,ValueError): return None
    @staticmethod
    def _time_string(value):
        if value is None:return None
        if hasattr(value,"strftime"):
            try:return value.strftime("%H:%M")
            except Exception:pass
        text=str(value).strip()
        try:return datetime.fromisoformat(text).strftime("%H:%M")
        except ValueError:pass
        m=re.search(r"(?:^|T|\s)(\d{2}):(\d{2})",text); return f"{m.group(1)}:{m.group(2)}" if m else None
    @staticmethod
    def _trade_number(trade_id):
        m=re.search(r"PAPER-(\d+)$",str(trade_id).strip().upper()); return int(m.group(1)) if m else 0
    @staticmethod
    def _candle_key(value):
        if value is None:return ""
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if pd.isna(parsed):return str(value)
            if getattr(parsed,"tzinfo",None) is None:parsed=parsed.tz_localize(INDIA_TZ)
            else:parsed=parsed.tz_convert(INDIA_TZ)
            return parsed.isoformat()
        except Exception:return str(value)
    @staticmethod
    def _session_date(value):
        if value is None:return None
        try:
            parsed=pd.to_datetime(value,errors="coerce")
            if pd.isna(parsed):return None
            if getattr(parsed,"tzinfo",None) is None:parsed=parsed.tz_localize(INDIA_TZ)
            else:parsed=parsed.tz_convert(INDIA_TZ)
            return parsed.date()
        except Exception:return None
    def _valid_open_position(self,key,position):
        if not isinstance(position,dict):return False
        symbol=str(position.get("symbol",key)).strip().upper(); signal=str(position.get("signal","")).strip().upper(); entry=self._number(position.get("entry")); stop=self._number(position.get("stop_loss")); target=self._number(position.get("target")); quantity=self._number(position.get("quantity"))
        return bool(symbol and symbol==str(key).strip().upper() and signal in {"BUY","SELL"} and entry and entry>0 and stop and stop>0 and target and target>0 and quantity and quantity>0 and int(quantity)==quantity and position.get("trade_id"))
    def _restore_state(self):
        path=self._state_path()
        try:
            restore_json(path,path.replace(os.sep,"/"))
            if not os.path.exists(path):return
            with open(path,"r",encoding="utf-8") as file: state=json.load(file)
            if not isinstance(state,dict):raise ValueError("Persisted paper state must be an object")
            if int(state.get("state_version",0) or 0)!=STATE_VERSION:
                print("Legacy paper state detected; starting clean."); self._reset_state_file(path); return
            restored_open=state.get("open_positions",{}); restored_closed=state.get("closed_positions",[])
            if not isinstance(restored_open,dict) or not isinstance(restored_closed,list):
                print("Invalid persisted paper state collections detected; starting clean."); self._reset_state_file(path); return
            self.open_positions={str(symbol).strip().upper():position for symbol,position in restored_open.items() if self._valid_open_position(symbol,position)}
            self.closed_positions=[position for position in restored_closed if isinstance(position,dict)]
            saved_date=self._session_date(state.get("session_date") or state.get("saved_at")); today=datetime.now(INDIA_TZ).date()
            if saved_date is not None and saved_date != today:
                print(f"Stale paper session state ({saved_date}) detected; clearing old session results for {today}."); self.open_positions={}; self.closed_positions=[]
            for position in self.open_positions.values():
                position.setdefault("mae",0.0); position.setdefault("mfe",0.0); position.setdefault("last_processed_candle",self._candle_key(position.get("entry_time")))
            for position in self.closed_positions:
                position.setdefault("mae",0.0); position.setdefault("mfe",0.0); position.setdefault("exit_reason","")
            self.total_capital=float(state.get("total_capital",TOTAL_CAPITAL) or TOTAL_CAPITAL)
            counters=[self._trade_number(p.get("trade_id")) for p in self.open_positions.values()]+[self._trade_number(p.get("trade_id")) for p in self.closed_positions]; counter=int(state.get("trade_counter",0) or 0)
            try:
                journal=pd.read_csv(TRADE_LOG_FILE)
                if "trade_id" in journal.columns:counters.extend(journal["trade_id"].map(self._trade_number).tolist())
            except Exception:pass
            self.trade_counter=max([counter,*counters],default=0)
            self.used_capital=round(sum(float(p.get("entry",0) or 0)*int(float(p.get("quantity",0) or 0)) for p in self.open_positions.values()),2); self.available_capital=round(self.total_capital-self.used_capital,2)
            if self.available_capital<0:raise ValueError("Persisted open positions exceed total capital")
            if saved_date is not None and saved_date != today:self._save_state()
        except Exception as error:print(f"Paper state restore skipped: {type(error).__name__}: {error}")
    @staticmethod
    def _reset_state_file(path):
        try:os.remove(path)
        except OSError:pass
    def _save_state(self):
        path=self._state_path(); os.makedirs(os.path.dirname(path),exist_ok=True); state={"state_version":STATE_VERSION,"strategy":"NIFTY_500_PDH_PDL_OPEN_REVERSAL","session_date":datetime.now(INDIA_TZ).date().isoformat(),"open_positions":self.open_positions,"closed_positions":self.closed_positions,"trade_counter":self.trade_counter,"total_capital":self.total_capital,"available_capital":self.available_capital,"used_capital":self.used_capital,"saved_at":datetime.now(INDIA_TZ).isoformat()}
        try:
            with open(path,"w",encoding="utf-8") as file:json.dump(state,file,ensure_ascii=False,indent=2,default=str)
            sync_json(path,path.replace(os.sep,"/"),"Save NIFTY 500 paper-trading state")
        except Exception as error:print(f"Paper state sync skipped: {type(error).__name__}: {error}")
    def has_open_position(self,symbol):return str(symbol).strip().upper() in self.open_positions
    def _validate_trade(self,trade):
        if not isinstance(trade,dict):return None,"Trade must be a dictionary"
        if not self.paper_trading:return None,"Paper trading is disabled"
        if self.live_trading:return None,"Live trading must remain disabled"
        if not trade.get("approved",False):return None,"Trade has not been approved"
        symbol=str(trade.get("symbol","")).strip().upper(); signal=str(trade.get("signal","")).strip().upper(); entry=self._number(trade.get("entry")); stop=self._number(trade.get("stop_loss")); target=self._number(trade.get("target")); quantity_number=self._number(trade.get("quantity")); actual_risk=self._number(trade.get("actual_risk"))
        if not symbol:return None,"Missing symbol"
        if signal not in {"BUY","SELL"}:return None,"Invalid signal"
        if entry is None or stop is None or target is None or quantity_number is None:return None,"Invalid trade values"
        if entry<=0 or stop<=0 or target<=0:return None,"Prices must be positive"
        if quantity_number<=0 or int(quantity_number)!=quantity_number:return None,"Quantity must be a positive whole number"
        quantity=int(quantity_number)
        if signal=="BUY" and (stop>=entry or target<=entry):return None,"Invalid BUY stop/target"
        if signal=="SELL" and (stop<=entry or target>=entry):return None,"Invalid SELL stop/target"
        risk_per_share=abs(entry-stop); risk=round(risk_per_share*quantity,2); reward=round(abs(target-entry)*quantity,2); rr=reward/risk if risk>0 else 0.0
        if risk<float(MIN_REQUIRED_RISK):return None,f"Actual risk Rs {risk:.2f} is below minimum {float(MIN_REQUIRED_RISK):.2f}"
        if risk>float(MAX_RISK_PER_TRADE):return None,f"Actual risk Rs {risk:.2f} exceeds maximum {float(MAX_RISK_PER_TRADE):.2f}"
        if rr<float(MIN_RR_RATIO):return None,f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}"
        if actual_risk is not None and abs(actual_risk-risk)>1.0:return None,"Approved risk does not match calculated risk"
        entry_hhmm=self._time_string(trade.get("entry_time") or datetime.now(INDIA_TZ))
        if entry_hhmm is None or entry_hhmm<self.trading_start or entry_hhmm>self.last_entry_time:return None,"Entry time is outside the allowed window"
        position_value=round(entry*quantity,2)
        if position_value>self.available_capital:return None,"Insufficient available capital"
        if self.has_open_position(symbol):return None,f"{symbol} already has an open position"
        if len(self.open_positions)>=MAX_OPEN_POSITIONS:return None,"Maximum open positions reached"
        return {"symbol":symbol,"signal":signal,"entry_time":trade.get("entry_time"),"entry":round(entry,4),"stop_loss":round(stop,4),"target":round(target,4),"quantity":quantity,"risk":risk,"reward":reward,"rr":round(rr,4),"position_value":position_value},None
    def open_trade(self,trade):
        validated,reason=self._validate_trade(trade)
        if validated is None:return {"opened":False,"reason":reason}
        self.trade_counter+=1; trade_id=f"PAPER-{self.trade_counter:04d}"; position={"trade_id":trade_id,"symbol":validated["symbol"],"stock":validated["symbol"],"signal":validated["signal"],"buy_sell":validated["signal"],"entry_time":validated["entry_time"],"entry":validated["entry"],"stop_loss":validated["stop_loss"],"target":validated["target"],"quantity":validated["quantity"],"risk":validated["risk"],"reward":validated["reward"],"rr":validated["rr"],"mae":0.0,"mfe":0.0,"last_processed_candle":self._candle_key(validated["entry_time"]),"status":"OPEN","exit_time":None,"exit_price":None,"exit_reason":None,"pnl":None}; ignored={"approved","reasons","min_rr_ratio","min_required_risk","max_risk","capital","trade_count"}
        for field,value in trade.items():
            if field not in ignored and field not in position and value is not None:position[field]=value
        position["risk_per_share"]=round(abs(validated["entry"]-validated["stop_loss"]),4); position["actual_risk"]=validated["risk"]; position["position_value"]=validated["position_value"]; self.open_positions[validated["symbol"]]=position; self.used_capital=round(self.used_capital+validated["position_value"],2); self.available_capital=round(self.total_capital-self.used_capital,2); self._save_state(); return {"opened":True,"trade_id":trade_id,"position":position.copy()}
    @staticmethod
    def calculate_pnl(signal,entry,exit_price,quantity):
        if signal=="BUY":return round((exit_price-entry)*quantity,2)
        if signal=="SELL":return round((entry-exit_price)*quantity,2)
        return 0.0
    def _update_excursions(self,position,high,low):
        entry=float(position.get("entry",0) or 0); qty=int(float(position.get("quantity",0) or 0)); signal=str(position.get("signal","")).upper()
        if entry<=0 or qty<=0:return
        if signal=="BUY":favorable=max(0.0,(float(high)-entry)*qty); adverse=max(0.0,(entry-float(low))*qty)
        else:favorable=max(0.0,(entry-float(low))*qty); adverse=max(0.0,(float(high)-entry)*qty)
        position["mfe"]=round(max(float(position.get("mfe",0) or 0),favorable),2); position["mae"]=round(max(float(position.get("mae",0) or 0),adverse),2)
    def close_position(self,symbol,exit_price,exit_time,reason):
        symbol=str(symbol).strip().upper()
        if not self.has_open_position(symbol):return None
        exit_price=self._number(exit_price)
        if exit_price is None or exit_price<=0:return None
        position=self.open_positions[symbol]; pnl=self.calculate_pnl(position["signal"],position["entry"],exit_price,position["quantity"]); position.update({"status":"CLOSED","exit_time":exit_time,"exit_price":round(exit_price,4),"exit_reason":reason,"pnl":pnl}); closed=position.copy(); self.closed_positions.append(closed); position_value=round(float(position["entry"])*int(position["quantity"]),2); self.used_capital=round(max(0.0,self.used_capital-position_value),2); self.available_capital=round(self.total_capital-self.used_capital,2); del self.open_positions[symbol]; self._save_state(); return closed
    def process_candle(self,symbol,candle):
        symbol=str(symbol).strip().upper()
        if not self.has_open_position(symbol):return None
        if not isinstance(candle,dict):
            try:candle=candle.to_dict()
            except Exception:return None
        high=self._number(candle.get("High")); low=self._number(candle.get("Low")); close=self._number(candle.get("Close")); candle_time=candle.get("Datetime")
        if high is None or low is None or close is None:return None
        key=self._candle_key(candle_time); exit_timestamp=key or candle_time; position=self.open_positions[symbol]; last=self._candle_key(position.get("last_processed_candle"))
        if key and last and key<=last:return None
        self._update_excursions(position,high,low); signal=position["signal"]; stop=float(position["stop_loss"]); target=float(position["target"])
        if signal=="BUY":sl_hit,target_hit=low<=stop,high>=target
        else:sl_hit,target_hit=high>=stop,low<=target
        position["last_processed_candle"]=key or last
        if sl_hit and target_hit:return self.close_position(symbol,stop,exit_timestamp,"AMBIGUOUS_CANDLE_STOP_FIRST")
        if sl_hit:return self.close_position(symbol,stop,exit_timestamp,"STOP_LOSS")
        if target_hit:return self.close_position(symbol,target,exit_timestamp,"TARGET")
        self._save_state(); return None
    def summary(self):
        pnl_values=[self._number(t.get("pnl")) or 0.0 for t in self.closed_positions]; return {"open_positions":len(self.open_positions),"closed_positions":len(self.closed_positions),"winning_trades":sum(1 for pnl in pnl_values if pnl>0),"losing_trades":sum(1 for pnl in pnl_values if pnl<0),"total_pnl":round(sum(pnl_values),2),"total_capital":self.total_capital,"available_capital":round(self.available_capital,2),"used_capital":round(self.used_capital,2)}
