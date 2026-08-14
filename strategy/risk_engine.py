"""Risk and position sizing gate for the NIFTY 500 paper strategy."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import TOTAL_CAPITAL, MAX_RISK_PER_TRADE, MIN_REQUIRED_RISK, MAX_TRADES_PER_STOCK, MIN_RR_RATIO, TRADE_LOG_FILE

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class RiskEngine:
    """Final safety gate. Position size is derived from the real entry/SL distance."""

    def __init__(self):
        self.total_capital = float(TOTAL_CAPITAL)
        self.max_risk_per_trade = float(MAX_RISK_PER_TRADE)
        self.min_required_risk = float(MIN_REQUIRED_RISK)
        self.max_trades_per_stock = int(MAX_TRADES_PER_STOCK)
        self.trade_counts = {}
        self.restore_today_trade_counts()

    @staticmethod
    def _number(value):
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _today_ist():
        return datetime.now(INDIA_TZ).date()

    @staticmethod
    def _entry_date_ist(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            if getattr(parsed, "tzinfo", None) is None:
                return parsed.date()
            return parsed.tz_convert(INDIA_TZ).date()
        except Exception:
            return None

    def restore_today_trade_counts(self):
        self.trade_counts = {}
        path = Path(TRADE_LOG_FILE)
        if not path.exists():
            return
        try:
            df = pd.read_csv(path)
            if df.empty or "symbol" not in df.columns or "entry_time" not in df.columns:
                return
            today = self._today_ist()
            for row in df.itertuples(index=False):
                if self._entry_date_ist(getattr(row, "entry_time", "")) != today:
                    continue
                status = str(getattr(row, "status", "")).strip().upper()
                if status.startswith("MISSED_CAPITAL"):
                    continue
                symbol = str(getattr(row, "symbol", "")).strip().upper()
                if symbol:
                    self.trade_counts[symbol] = self.trade_counts.get(symbol, 0) + 1
        except Exception:
            self.trade_counts = {}

    def get_trade_count(self, symbol):
        return self.trade_counts.get(str(symbol).strip().upper(), 0)

    def stock_trade_allowed(self, symbol):
        return self.get_trade_count(symbol) < self.max_trades_per_stock

    def register_trade(self, symbol):
        key = str(symbol).strip().upper()
        self.trade_counts[key] = self.get_trade_count(key) + 1
        return self.trade_counts[key]

    def calculate_risk(self, signal, entry, stop_loss, quantity):
        entry = self._number(entry)
        stop_loss = self._number(stop_loss)
        quantity = self._number(quantity)
        side = str(signal).strip().upper()
        if entry is None or stop_loss is None or quantity is None or quantity <= 0:
            return None
        risk_per_share = entry - stop_loss if side == "BUY" else stop_loss - entry if side == "SELL" else None
        if risk_per_share is None or risk_per_share <= 0:
            return None
        return {"risk_per_share": round(risk_per_share, 4), "actual_risk": round(risk_per_share * quantity, 2), "position_value": round(entry * quantity, 2)}

    def validate(self, trade, check_trade_count=True):
        if not isinstance(trade, dict):
            return {"approved": False, "reasons": ["Trade must be a dictionary"]}
        symbol = str(trade.get("symbol", "")).strip().upper()
        signal = str(trade.get("signal", "")).strip().upper()
        entry = self._number(trade.get("entry")); stop = self._number(trade.get("stop_loss")); target = self._number(trade.get("target")); reasons = []
        if not symbol: reasons.append("Missing symbol")
        if signal not in {"BUY", "SELL"}: reasons.append("Signal must be BUY or SELL")
        if entry is None or entry <= 0: reasons.append("Invalid entry price")
        if stop is None or stop <= 0: reasons.append("Invalid stop loss")
        if target is None or target <= 0: reasons.append("Invalid target")
        if entry is not None and stop is not None:
            if signal == "BUY" and stop >= entry: reasons.append("BUY stop loss must be below entry")
            if signal == "SELL" and stop <= entry: reasons.append("SELL stop loss must be above entry")
        if entry is not None and target is not None:
            if signal == "BUY" and target <= entry: reasons.append("BUY target must be above entry")
            if signal == "SELL" and target >= entry: reasons.append("SELL target must be below entry")
        if reasons:
            return {"approved": False, "symbol": symbol, "signal": signal, "reasons": reasons}

        risk_per_share = abs(entry - stop)
        max_risk_qty = int(self.max_risk_per_trade // risk_per_share)
        capital_qty = int(self.total_capital // entry)
        quantity = min(max_risk_qty, capital_qty)
        if quantity <= 0:
            return {"approved": False, "symbol": symbol, "signal": signal, "reasons": ["Risk distance is too large for capital/risk budget"]}

        actual_risk = round(risk_per_share * quantity, 2)
        position_value = round(entry * quantity, 2)
        reward_per_share = (target - entry) if signal == "BUY" else (entry - target)
        reward = round(reward_per_share * quantity, 2)
        rr = reward / actual_risk if actual_risk > 0 else 0.0
        if rr < float(MIN_RR_RATIO): reasons.append(f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}")
        if actual_risk < self.min_required_risk: reasons.append(f"Actual risk Rs {actual_risk:.2f} is below minimum required Rs {self.min_required_risk:.2f}")
        if actual_risk > self.max_risk_per_trade: reasons.append(f"Actual risk Rs {actual_risk:.2f} exceeds maximum Rs {self.max_risk_per_trade:.2f}")
        if position_value > self.total_capital: reasons.append(f"Position value Rs {position_value:.2f} exceeds capital Rs {self.total_capital:.2f}")
        if check_trade_count and not self.stock_trade_allowed(symbol): reasons.append(f"{symbol} already reached maximum trades per stock ({self.max_trades_per_stock})")

        return {"approved": not reasons, "symbol": symbol, "signal": signal, "entry": round(entry, 4), "stop_loss": round(stop, 4), "target": round(target, 4), "quantity": int(quantity), "risk_per_share": round(risk_per_share, 4), "actual_risk": actual_risk, "reward": reward, "rr": round(rr, 4), "min_rr_ratio": float(MIN_RR_RATIO), "position_value": position_value, "min_required_risk": self.min_required_risk, "max_risk": self.max_risk_per_trade, "capital": self.total_capital, "reasons": reasons}

    def approve_trade(self, trade):
        result = self.validate(trade, check_trade_count=True)
        if not result.get("approved"):
            return result
        self.register_trade(result["symbol"])
        result["trade_count"] = self.get_trade_count(result["symbol"])
        return result

    def calculate_position_size(self, entry, stop_loss, available_capital=None):
        entry = self._number(entry); stop_loss = self._number(stop_loss)
        if entry is None or stop_loss is None or entry <= 0 or entry == stop_loss:
            return 0
        risk_per_share = abs(entry - stop_loss)
        risk_qty = int(self.max_risk_per_trade // risk_per_share)
        capital = self.total_capital if available_capital is None else float(available_capital)
        return max(0, min(risk_qty, int(capital // entry)))
