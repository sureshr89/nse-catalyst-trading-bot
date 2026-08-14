"""Persistent paper-trade execution engine for the NIFTY 100 strategy."""

import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import (
    PAPER_TRADING,
    LIVE_TRADING,
    TRADING_START,
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    MARKET_CLOSE,
    TOTAL_CAPITAL,
    MAX_OPEN_POSITIONS,
    MIN_REQUIRED_RISK,
    MAX_RISK_PER_TRADE,
    MIN_RR_RATIO,
    TRADE_LOG_FILE,
)
from market.price_data import PriceData
from papertrade.persistent_storage import restore_json, sync_json

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class PaperTradeEngine:
    """Simulated execution engine. Live trading is deliberately prohibited."""

    def __init__(self):
        self.paper_trading = bool(PAPER_TRADING)
        self.live_trading = bool(LIVE_TRADING)
        self.trading_start = TRADING_START
        self.last_entry_time = LAST_ENTRY_TIME
        self.square_off_time = SQUARE_OFF_TIME
        self.market_close = MARKET_CLOSE
        self.open_positions = {}
        self.closed_positions = []
        self.trade_counter = 0
        self.total_capital = float(TOTAL_CAPITAL)
        self.available_capital = float(TOTAL_CAPITAL)
        self.used_capital = 0.0
        self.price_data = PriceData()
        self._restore_state()

    def _state_path(self):
        return os.path.join("outputs", "paper_engine_state.json")

    @staticmethod
    def _number(value):
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _time_string(value):
        if value is None:
            return None
        if hasattr(value, "strftime"):
            try:
                return value.strftime("%H:%M")
            except Exception:
                pass
        text = str(value).strip()
        try:
            return datetime.fromisoformat(text).strftime("%H:%M")
        except ValueError:
            pass
        match = re.search(r"(?:^|T|\s)(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:[+\-Z]|$)", text)
        return f"{match.group(1)}:{match.group(2)}" if match else None

    @staticmethod
    def _trade_number(trade_id):
        match = re.search(r"PAPER-(\d+)$", str(trade_id).strip().upper())
        return int(match.group(1)) if match else 0

    def _restore_state(self):
        path = self._state_path()
        try:
            restore_json(path, path.replace(os.sep, "/"))
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as file:
                state = json.load(file)
            self.open_positions = state.get("open_positions", {}) or {}
            self.closed_positions = state.get("closed_positions", []) or []
            self.total_capital = float(state.get("total_capital", TOTAL_CAPITAL) or TOTAL_CAPITAL)

            counters = [self._trade_number(p.get("trade_id")) for p in self.open_positions.values()]
            counters += [self._trade_number(p.get("trade_id")) for p in self.closed_positions]
            counter = int(state.get("trade_counter", 0) or 0)
            try:
                journal = pd.read_csv(TRADE_LOG_FILE)
                if "trade_id" in journal.columns:
                    counters.extend(journal["trade_id"].map(self._trade_number).tolist())
            except Exception:
                pass
            self.trade_counter = max([counter, *counters], default=0)
            self.used_capital = round(sum(
                float(p.get("entry", 0) or 0) * int(float(p.get("quantity", 0) or 0))
                for p in self.open_positions.values()
            ), 2)
            self.available_capital = round(self.total_capital - self.used_capital, 2)
            if self.available_capital < 0:
                raise ValueError("Persisted open positions exceed total capital")
            print(f"Persistent paper state restored: {len(self.open_positions)} open position(s)")
        except Exception as error:
            print(f"Paper state restore skipped: {type(error).__name__}: {error}")

    def _save_state(self):
        path = self._state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "trade_counter": self.trade_counter,
            "total_capital": self.total_capital,
            "available_capital": self.available_capital,
            "used_capital": self.used_capital,
            "saved_at": datetime.now().isoformat(),
        }
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, indent=2, default=str)
            sync_json(path, path.replace(os.sep, "/"), "Persist paper trading runtime state")
        except Exception as error:
            print(f"Paper state sync skipped: {type(error).__name__}: {error}")

    def has_open_position(self, symbol):
        return str(symbol).strip().upper() in self.open_positions

    def _validate_trade(self, trade):
        if not isinstance(trade, dict): return None, "Trade must be a dictionary"
        if not self.paper_trading: return None, "Paper trading is disabled"
        if self.live_trading: return None, "Live trading must remain disabled while using PaperTradeEngine"
        if not trade.get("approved", False): return None, "Trade has not been approved by RiskEngine"
        symbol = str(trade.get("symbol", "")).strip().upper(); signal = str(trade.get("signal", "")).strip().upper()
        entry = self._number(trade.get("entry")); stop = self._number(trade.get("stop_loss")); target = self._number(trade.get("target")); quantity_number = self._number(trade.get("quantity")); actual_risk = self._number(trade.get("actual_risk"))
        if not symbol: return None, "Missing symbol"
        if signal not in {"BUY", "SELL"}: return None, "Invalid signal"
        if entry is None or stop is None or target is None or quantity_number is None: return None, "Invalid trade values"
        if entry <= 0 or stop <= 0 or target <= 0: return None, "Prices must be positive"
        if quantity_number <= 0 or int(quantity_number) != quantity_number: return None, "Quantity must be a positive whole number"
        quantity = int(quantity_number)
        if signal == "BUY" and (stop >= entry or target <= entry): return None, "Invalid BUY stop/target"
        if signal == "SELL" and (stop <= entry or target >= entry): return None, "Invalid SELL stop/target"
        risk_per_share = abs(entry - stop); risk = round(risk_per_share * quantity, 2); reward = round(abs(target - entry) * quantity, 2); rr = reward / risk if risk > 0 else 0.0
        if risk < float(MIN_REQUIRED_RISK): return None, f"Actual risk ₹{risk:.2f} is below minimum ₹{float(MIN_REQUIRED_RISK):.2f}"
        if risk > float(MAX_RISK_PER_TRADE): return None, f"Actual risk ₹{risk:.2f} exceeds maximum ₹{float(MAX_RISK_PER_TRADE):.2f}"
        if rr < float(MIN_RR_RATIO): return None, f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}"
        if actual_risk is not None and abs(actual_risk - risk) > 1.0: return None, f"Approved risk ₹{actual_risk:.2f} does not match calculated risk ₹{risk:.2f}"
        entry_time = trade.get("entry_time") or datetime.now(); entry_hhmm = self._time_string(entry_time)
        if entry_hhmm is None: return None, "Unable to determine entry time"
        if entry_hhmm < self.trading_start or entry_hhmm > self.last_entry_time: return None, f"Entry time {entry_hhmm} is outside {self.trading_start}-{self.last_entry_time} IST"
        position_value = round(entry * quantity, 2)
        if position_value > self.available_capital: return None, "Insufficient available capital"
        if self.has_open_position(symbol): return None, f"{symbol} already has an open position"
        if len(self.open_positions) >= MAX_OPEN_POSITIONS: return None, "Maximum open positions reached"
        return {"symbol": symbol, "signal": signal, "entry_time": entry_time, "entry": round(entry, 4), "stop_loss": round(stop, 4), "target": round(target, 4), "quantity": quantity, "risk": risk, "reward": reward, "rr": round(rr, 4), "position_value": position_value}, None

    def open_trade(self, trade):
        validated, reason = self._validate_trade(trade)
        if validated is None: return {"opened": False, "reason": reason}
        self.trade_counter += 1; trade_id = f"PAPER-{self.trade_counter:04d}"
        position = {"trade_id": trade_id, "symbol": validated["symbol"], "stock": validated["symbol"], "signal": validated["signal"], "buy_sell": validated["signal"], "entry_time": validated["entry_time"], "entry": validated["entry"], "stop_loss": validated["stop_loss"], "target": validated["target"], "quantity": validated["quantity"], "risk": validated["risk"], "reward": validated["reward"], "rr": validated["rr"], "status": "OPEN", "exit_time": None, "exit_price": None, "exit_reason": None, "pnl": None}
        ignored = {"approved", "reasons", "min_rr_ratio", "min_required_risk", "max_risk", "capital", "trade_count"}
        for field, value in trade.items():
            if field not in ignored and field not in position and value is not None: position[field] = value
        position["risk_per_share"] = round(abs(validated["entry"] - validated["stop_loss"]), 4); position["actual_risk"] = validated["risk"]; position["position_value"] = validated["position_value"]
        self.open_positions[validated["symbol"]] = position; self.used_capital = round(self.used_capital + validated["position_value"], 2); self.available_capital = round(self.total_capital - self.used_capital, 2); self._save_state()
        return {"opened": True, "trade_id": trade_id, "position": position.copy()}

    @staticmethod
    def calculate_pnl(signal, entry, exit_price, quantity):
        if signal == "BUY": pnl = (exit_price - entry) * quantity
        elif signal == "SELL": pnl = (entry - exit_price) * quantity
        else: pnl = 0.0
        return round(pnl, 2)

    def close_position(self, symbol, exit_price, exit_time, reason):
        symbol = str(symbol).strip().upper()
        if not self.has_open_position(symbol): return None
        exit_price = self._number(exit_price)
        if exit_price is None or exit_price <= 0: return None

        # Mandatory square-off uses the latest available market price, not the
        # previous completed 1-minute candle. The execution timestamp is rounded
        # to the square-off minute so TATACAP and every other remaining position
        # are consistently recorded at 15:00 IST.
        if str(reason).upper() == "SQUARE_OFF":
            try:
                latest = self.price_data.get_latest_available_1m(symbol)
                if latest:
                    latest_price = self._number(latest.get("Close", latest.get("close")))
                    latest_time = latest.get("Datetime", latest.get("datetime"))
                    if latest_price is not None and latest_price > 0:
                        exit_price = latest_price
                    if latest_time is not None:
                        exit_time = latest_time
                if self._time_string(exit_time) != self.square_off_time:
                    now = datetime.now(INDIA_TZ)
                    if now.strftime("%H:%M") >= self.square_off_time:
                        exit_time = now.replace(second=0, microsecond=0)
            except Exception as error:
                print(f"Latest square-off price unavailable for {symbol}; using supplied price: {error}")

        position = self.open_positions[symbol]
        pnl = self.calculate_pnl(position["signal"], position["entry"], exit_price, position["quantity"])
        position.update({"status": "CLOSED", "exit_time": exit_time, "exit_price": round(exit_price, 4), "exit_reason": reason, "pnl": pnl})
        closed = position.copy(); self.closed_positions.append(closed)
        position_value = round(float(position["entry"]) * int(position["quantity"]), 2)
        self.used_capital = round(max(0.0, self.used_capital - position_value), 2); self.available_capital = round(self.total_capital - self.used_capital, 2)
        del self.open_positions[symbol]; self._save_state(); return closed

    def process_candle(self, symbol, candle):
        symbol = str(symbol).strip().upper()
        if not self.has_open_position(symbol): return None
        if not isinstance(candle, dict):
            try: candle = candle.to_dict()
            except Exception: return None
        high = self._number(candle.get("High", candle.get("high"))); low = self._number(candle.get("Low", candle.get("low"))); close = self._number(candle.get("Close", candle.get("close"))); candle_time = candle.get("Datetime", candle.get("datetime"))
        if high is None or low is None or close is None: return None
        position = self.open_positions[symbol]; signal = position["signal"]; stop = float(position["stop_loss"]); target = float(position["target"])
        if signal == "BUY": sl_hit, target_hit = low <= stop, high >= target
        else: sl_hit, target_hit = high >= stop, low <= target
        if sl_hit: return self.close_position(symbol, stop, candle_time, "STOP_LOSS")
        if target_hit: return self.close_position(symbol, target, candle_time, "TARGET")
        candle_hhmm = self._time_string(candle_time)
        if candle_hhmm is not None and candle_hhmm >= self.square_off_time: return self.close_position(symbol, close, candle_time, "SQUARE_OFF")
        return None

    def square_off_all(self, prices, exit_time):
        closed=[]
        for symbol in list(self.open_positions):
            if symbol not in prices: continue
            result=self.close_position(symbol,prices[symbol],exit_time,"SQUARE_OFF")
            if result is not None: closed.append(result)
        return closed

    def summary(self):
        pnl_values=[self._number(t.get("pnl")) or 0.0 for t in self.closed_positions]
        return {"open_positions":len(self.open_positions),"closed_positions":len(self.closed_positions),"winning_trades":sum(1 for pnl in pnl_values if pnl>0),"losing_trades":sum(1 for pnl in pnl_values if pnl<0),"total_pnl":round(sum(pnl_values),2),"total_capital":self.total_capital,"available_capital":round(self.available_capital,2),"used_capital":round(self.used_capital,2)}
