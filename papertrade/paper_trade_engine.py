"""Persistent paper-trade execution engine for the NIFTY 500 strategy."""
import json
import os
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import (
    PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME,
    SQUARE_OFF_TIME, MARKET_CLOSE, TOTAL_CAPITAL, MAX_OPEN_POSITIONS,
    MIN_REQUIRED_RISK, MAX_RISK_PER_TRADE, MIN_RR_RATIO, TRADE_LOG_FILE,
)
from papertrade.persistent_storage import restore_json, sync_json

INDIA_TZ = ZoneInfo("Asia/Kolkata")
STATE_VERSION = 8


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
        from market.price_data import PriceData
        self.price_data = PriceData()
        self._restore_state()

    def _state_path(self):
        return os.path.join("outputs", "paper_engine_state.json")

    @staticmethod
    def _number(value):
        try:
            n = float(value)
            return n if n == n else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _candle_key(value):
        if value is None:
            return ""
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return str(value)
            parsed = parsed.tz_localize(INDIA_TZ) if getattr(parsed, "tzinfo", None) is None else parsed.tz_convert(INDIA_TZ)
            return parsed.isoformat()
        except Exception:
            return str(value)

    @staticmethod
    def _session_date(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            parsed = parsed.tz_localize(INDIA_TZ) if getattr(parsed, "tzinfo", None) is None else parsed.tz_convert(INDIA_TZ)
            return parsed.date()
        except Exception:
            return None

    @staticmethod
    def _time_string(value):
        if value is None:
            return None
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass
        text = str(value).strip()
        try:
            return datetime.fromisoformat(text).strftime("%H:%M")
        except ValueError:
            match = re.search(r"(?:^|T|\s)(\d{2}):(\d{2})", text)
            return f"{match.group(1)}:{match.group(2)}" if match else None

    @staticmethod
    def _trade_number(trade_id):
        match = re.search(r"PAPER-(\d+)$", str(trade_id).strip().upper())
        return int(match.group(1)) if match else 0

    def _valid_open_position(self, key, position):
        if not isinstance(position, dict):
            return False
        symbol = str(position.get("symbol", key)).strip().upper()
        signal = str(position.get("signal", "")).strip().upper()
        entry = self._number(position.get("entry")); stop = self._number(position.get("stop_loss")); target = self._number(position.get("target")); qty = self._number(position.get("quantity"))
        return bool(symbol == str(key).strip().upper() and signal in {"BUY", "SELL"} and entry and entry > 0 and stop and stop > 0 and target and target > 0 and qty and qty > 0 and int(qty) == qty and position.get("trade_id"))

    def _migrate_state(self, state, version):
        state = dict(state)
        state.setdefault("open_positions", {})
        state.setdefault("closed_positions", [])
        state.setdefault("trade_counter", 0)
        state.setdefault("total_capital", TOTAL_CAPITAL)
        state.setdefault("available_capital", state.get("total_capital", TOTAL_CAPITAL))
        state.setdefault("used_capital", 0.0)
        state.setdefault("session_date", state.get("saved_at"))
        if not isinstance(state["open_positions"], dict) or not isinstance(state["closed_positions"], list):
            raise ValueError(f"Unsupported paper state collections in legacy version {version}")
        state["state_version"] = STATE_VERSION
        return state

    def _restore_state(self):
        path = self._state_path()
        try:
            restore_json(path, path.replace(os.sep, "/"))
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as file:
                state = json.load(file)
            version = int(state.get("state_version", 0) or 0)
            if version > STATE_VERSION:
                print(f"Future paper state version {version} detected; preserving it.")
                return
            if version < STATE_VERSION:
                state = self._migrate_state(state, version)
            self.open_positions = {str(k).strip().upper(): v for k, v in state.get("open_positions", {}).items() if self._valid_open_position(k, v)}
            self.closed_positions = [v for v in state.get("closed_positions", []) if isinstance(v, dict)]
            saved_date = self._session_date(state.get("session_date") or state.get("saved_at"))
            if saved_date is not None and saved_date != datetime.now(INDIA_TZ).date():
                self.open_positions = {}
                self.closed_positions = []
            for position in self.open_positions.values():
                position.setdefault("mae", 0.0)
                position.setdefault("mfe", 0.0)
                position.setdefault("last_processed_candle", self._candle_key(position.get("entry_time")))
                position.setdefault("last_live_price", None)
            self.total_capital = float(state.get("total_capital", TOTAL_CAPITAL) or TOTAL_CAPITAL)
            counters = [self._trade_number(p.get("trade_id")) for p in self.open_positions.values()] + [self._trade_number(p.get("trade_id")) for p in self.closed_positions]
            try:
                journal = pd.read_csv(TRADE_LOG_FILE)
                if "trade_id" in journal.columns:
                    counters.extend(journal["trade_id"].map(self._trade_number).tolist())
            except Exception:
                pass
            self.trade_counter = max([int(state.get("trade_counter", 0) or 0), *counters], default=0)
            self.used_capital = round(sum(float(p.get("entry", 0) or 0) * int(float(p.get("quantity", 0) or 0)) for p in self.open_positions.values()), 2)
            self.available_capital = round(self.total_capital - self.used_capital, 2)
            if self.available_capital < 0:
                raise ValueError("Persisted open positions exceed total capital")
            self._save_state()
        except Exception as error:
            print(f"Paper state restore skipped: {type(error).__name__}: {error}")

    def _save_state(self):
        path = self._state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "state_version": STATE_VERSION,
            "strategy": "NIFTY_500_PDH_PDL_OPEN_RETURN",
            "session_date": datetime.now(INDIA_TZ).date().isoformat(),
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "trade_counter": self.trade_counter,
            "total_capital": self.total_capital,
            "available_capital": self.available_capital,
            "used_capital": self.used_capital,
            "saved_at": datetime.now(INDIA_TZ).isoformat(),
        }
        temporary = f"{path}.{os.getpid()}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, indent=2, default=str)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
            sync_json(path, path.replace(os.sep, "/"), "Save NIFTY 500 paper-trading state")
        except Exception as error:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except Exception:
                pass
            print(f"Paper state sync skipped: {type(error).__name__}: {error}")

    def has_open_position(self, symbol):
        return str(symbol).strip().upper() in self.open_positions
