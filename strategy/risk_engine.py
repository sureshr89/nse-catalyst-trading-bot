"""Risk and position sizing gate for the NIFTY 500 paper strategy."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json

import pandas as pd

from config.settings import (
    TOTAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK,
    MAX_TRADES_PER_STOCK,
    MIN_RR_RATIO,
    DAILY_MAX_LOSS,
    TRADE_LOG_FILE,
)

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
                parsed = parsed.tz_localize(INDIA_TZ)
            else:
                parsed = parsed.tz_convert(INDIA_TZ)
            return parsed.date()
        except Exception:
            return None

    def restore_today_trade_counts(self):
        """Restore today's unique trades without letting one malformed journal row erase valid counts."""
        self.trade_counts = {}
        path = Path(TRADE_LOG_FILE)
        if not path.exists():
            return
        try:
            df = pd.read_csv(path)
        except Exception:
            return
        if df.empty or "symbol" not in df.columns or "entry_time" not in df.columns:
            return
        today = self._today_ist()
        seen_ids = set()
        for row in df.itertuples(index=False):
            try:
                if self._entry_date_ist(getattr(row, "entry_time", "")) != today:
                    continue
                status = str(getattr(row, "status", "")).strip().upper()
                if status.startswith("MISSED_CAPITAL"):
                    continue
                symbol = str(getattr(row, "symbol", "")).strip().upper()
                if not symbol:
                    continue
                trade_id = str(getattr(row, "trade_id", "")).strip()
                if trade_id:
                    unique_key = (symbol, trade_id)
                else:
                    signal = str(getattr(row, "signal", "")).strip().upper()
                    entry = str(getattr(row, "entry", "")).strip()
                    unique_key = (symbol, signal, str(getattr(row, "entry_time", "")).strip(), entry)
                if unique_key in seen_ids:
                    continue
                seen_ids.add(unique_key)
                self.trade_counts[symbol] = self.trade_counts.get(symbol, 0) + 1
            except Exception:
                continue

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
        return {
            "risk_per_share": round(risk_per_share, 4),
            "actual_risk": round(risk_per_share * quantity, 2),
            "position_value": round(entry * quantity, 2),
        }

    def _current_daily_risk_state(self):
        """Return today's realized P&L and worst-case loss of persisted open positions."""
        realized_pnl = 0.0
        trade_path = Path(TRADE_LOG_FILE)
        if trade_path.exists():
            try:
                df = pd.read_csv(trade_path)
                if not df.empty and "status" in df.columns and "exit_time" in df.columns and "pnl" in df.columns:
                    closed = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
                    if not closed.empty:
                        dates = closed["exit_time"].map(self._entry_date_ist)
                        pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
                        realized_pnl = float(pnl[dates.eq(self._today_ist())].sum())
            except Exception:
                realized_pnl = 0.0

        open_risk = 0.0
        state_path = Path("outputs") / "paper_engine_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
                if isinstance(positions, dict):
                    for position in positions.values():
                        if not isinstance(position, dict):
                            continue
                        entry = self._number(position.get("entry"))
                        stop = self._number(position.get("stop_loss"))
                        quantity = self._number(position.get("quantity"))
                        if entry is not None and stop is not None and quantity is not None and quantity > 0:
                            open_risk += abs(entry - stop) * quantity
            except Exception:
                open_risk = 0.0
        return round(realized_pnl, 2), round(open_risk, 2)

    def validate(self, trade, check_trade_count=True, available_capital=None):
        if not isinstance(trade, dict):
            return {"approved": False, "reasons": ["Trade must be a dictionary"]}
        symbol = str(trade.get("symbol", "")).strip().upper()
        signal = str(trade.get("signal", "")).strip().upper()
        entry = self._number(trade.get("entry"))
        stop = self._number(trade.get("stop_loss"))
        target = self._number(trade.get("target"))
        reasons = []
        capital = self.total_capital if available_capital is None else self._number(available_capital)
        if capital is None or capital <= 0:
            capital = 0.0
        if not symbol:
            reasons.append("Missing symbol")
        if signal not in {"BUY", "SELL"}:
            reasons.append("Signal must be BUY or SELL")
        if entry is None or entry <= 0:
            reasons.append("Invalid entry price")
        if stop is None or stop <= 0:
            reasons.append("Invalid stop loss")
        if target is None or target <= 0:
            reasons.append("Invalid target")
        if entry is not None and stop is not None:
            if signal == "BUY" and stop >= entry:
                reasons.append("BUY stop loss must be below entry")
            if signal == "SELL" and stop <= entry:
                reasons.append("SELL stop loss must be above entry")
        if entry is not None and target is not None:
            if signal == "BUY" and target <= entry:
                reasons.append("BUY target must be above entry")
            if signal == "SELL" and target >= entry:
                reasons.append("SELL target must be below entry")
        if reasons:
            return {"approved": False, "symbol": symbol, "signal": signal, "reasons": reasons}

        risk_per_share = abs(entry - stop)
        max_risk_qty = int(self.max_risk_per_trade // risk_per_share)
        capital_qty = int(capital // entry)
        quantity = min(max_risk_qty, capital_qty)
        if quantity <= 0:
            return {"approved": False, "symbol": symbol, "signal": signal, "reasons": ["Insufficient available capital for one share at the calculated entry price"]}

        actual_risk = round(risk_per_share * quantity, 2)
        position_value = round(entry * quantity, 2)
        reward_per_share = (target - entry) if signal == "BUY" else (entry - target)
        reward = round(reward_per_share * quantity, 2)
        rr = reward / actual_risk if actual_risk > 0 else 0.0
        if rr < float(MIN_RR_RATIO):
            reasons.append(f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}")
        if actual_risk < self.min_required_risk:
            reasons.append(f"Actual risk Rs {actual_risk:.2f} is below minimum required Rs {self.min_required_risk:.2f}")
        if actual_risk > self.max_risk_per_trade:
            reasons.append(f"Actual risk Rs {actual_risk:.2f} exceeds maximum Rs {self.max_risk_per_trade:.2f}")
        if position_value > capital:
            reasons.append(f"Position value Rs {position_value:.2f} exceeds available capital Rs {capital:.2f}")
        if check_trade_count and not self.stock_trade_allowed(symbol):
            reasons.append(f"{symbol} already reached maximum trades per stock ({self.max_trades_per_stock})")

        realized_pnl, open_risk = self._current_daily_risk_state()
        worst_case_pnl = realized_pnl - open_risk - actual_risk
        if worst_case_pnl < -float(DAILY_MAX_LOSS):
            reasons.append(
                f"Daily max-loss protection: realized Rs {realized_pnl:.2f} + open risk Rs {open_risk:.2f} + new risk Rs {actual_risk:.2f} exceeds Rs {float(DAILY_MAX_LOSS):.2f}"
            )

        return {
            "approved": not reasons,
            "symbol": symbol,
            "signal": signal,
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "target": round(target, 4),
            "quantity": int(quantity),
            "risk_per_share": round(risk_per_share, 4),
            "actual_risk": actual_risk,
            "reward": reward,
            "rr": round(rr, 4),
            "min_rr_ratio": float(MIN_RR_RATIO),
            "position_value": position_value,
            "min_required_risk": self.min_required_risk,
            "max_risk": self.max_risk_per_trade,
            "capital": capital,
            "reasons": reasons,
        }

    def approve_trade(self, trade, available_capital=None):
        result = self.validate(trade, check_trade_count=True, available_capital=available_capital)
        if not result.get("approved"):
            return result
        self.register_trade(result["symbol"])
        result["trade_count"] = self.get_trade_count(result["symbol"])
        return result

    def calculate_position_size(self, entry, stop_loss, available_capital=None):
        entry = self._number(entry)
        stop_loss = self._number(stop_loss)
        if entry is None or stop_loss is None or entry <= 0 or entry == stop_loss:
            return 0
        risk_per_share = abs(entry - stop_loss)
        risk_qty = int(self.max_risk_per_trade // risk_per_share)
        capital = self.total_capital if available_capital is None else float(available_capital)
        quantity = max(0, min(risk_qty, int(capital // entry)))
        if quantity <= 0:
            return 0
        actual_risk = round(risk_per_share * quantity, 2)
        if actual_risk < self.min_required_risk or actual_risk > self.max_risk_per_trade:
            return 0
        return quantity
