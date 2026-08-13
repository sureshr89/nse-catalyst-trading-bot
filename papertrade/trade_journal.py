"""Trade and signal journal with optional GitHub-backed persistence."""

import csv
import os
from datetime import datetime

import pandas as pd

from config.settings import TRADE_LOG_FILE, SIGNAL_LOG_FILE
from papertrade.persistent_storage import restore, sync


class TradeJournal:
    TRADE_COLUMNS = [
        "trade_id", "symbol", "stock", "industry", "sector", "signal", "buy_sell",
        "entry_time", "entry", "stop_loss", "target", "quantity",
        "exit_time", "exit_price", "exit_reason", "risk", "reward", "rr",
        "pnl", "risk_per_share", "actual_risk", "position_value",
        "breakout_level", "pdc", "today_open", "today_low", "today_high",
        "market_direction", "nifty100_direction", "industry_direction", "sector_direction",
        "stock_direction", "stock_today_direction", "previous_day_aligned", "previous_day_direction",
        "setup_type", "entry_candle_open", "entry_candle_close", "status",
    ]

    SIGNAL_COLUMNS = [
        "timestamp", "symbol", "industry", "sector", "signal",
        "market_direction", "nifty100_direction", "industry_direction", "sector_direction",
        "stock_direction", "stock_today_direction", "previous_day_aligned", "previous_day_direction",
        "breakout_level", "pdc", "today_open", "today_low", "today_high",
        "entry", "stop_loss", "target", "quantity", "risk_reward", "risk_per_share",
        "actual_risk", "position_value", "setup_type", "entry_candle_open", "entry_candle_close",
        "approved", "reason",
    ]

    EXIT_FIELDS = {"exit_time", "exit_price", "exit_reason", "pnl", "status"}

    def __init__(self, trade_file=TRADE_LOG_FILE, signal_file=SIGNAL_LOG_FILE):
        self.trade_file = trade_file
        self.signal_file = signal_file
        self._prepare_files()
        restore(self.trade_file, self.trade_file.replace(os.sep, "/"))
        restore(self.signal_file, self.signal_file.replace(os.sep, "/"))
        self._prepare_files()

    def _prepare_files(self):
        for path, columns in (
            (self.trade_file, self.TRADE_COLUMNS),
            (self.signal_file, self.SIGNAL_COLUMNS),
        ):
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            if not os.path.exists(path):
                with open(path, "w", newline="", encoding="utf-8") as file:
                    csv.DictWriter(file, fieldnames=columns).writeheader()
                continue
            try:
                df = pd.read_csv(path)
                missing = [column for column in columns if column not in df.columns]
                for column in missing:
                    df[column] = ""
                df = df.reindex(columns=columns)
                df.to_csv(path, index=False)
            except (FileNotFoundError, pd.errors.EmptyDataError):
                with open(path, "w", newline="", encoding="utf-8") as file:
                    csv.DictWriter(file, fieldnames=columns).writeheader()

    @staticmethod
    def _value(value):
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return value

    @staticmethod
    def _normalise_signal_value(value):
        """Create a stable comparison value for signal de-duplication."""
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.8f}"
        text = str(value).strip()
        try:
            number = float(text)
            return f"{number:.8f}"
        except (TypeError, ValueError):
            return text.upper()

    def signal_key(self, signal):
        """Return the setup identity, deliberately excluding scan timestamp."""
        fields = (
            "symbol", "signal", "entry", "stop_loss", "target", "quantity",
            "breakout_level", "setup_type", "entry_candle_open", "entry_candle_close",
        )
        return tuple(self._normalise_signal_value(signal.get(field, "")) for field in fields)

    def signal_exists(self, signal):
        """Check persistent signal history so restarts cannot create duplicates."""
        try:
            df = pd.read_csv(self.signal_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return False
        if df.empty:
            return False
        key = self.signal_key(signal)
        available = [
            "symbol", "signal", "entry", "stop_loss", "target", "quantity",
            "breakout_level", "setup_type", "entry_candle_open", "entry_candle_close",
        ]
        for column in available:
            if column not in df.columns:
                df[column] = ""
        existing_keys = set()
        for _, row in df.iterrows():
            existing_keys.add(self.signal_key(row.to_dict()))
        return key in existing_keys

    def trade_exists(self, trade_id):
        if not trade_id:
            return False
        try:
            df = pd.read_csv(self.trade_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return False
        if df.empty or "trade_id" not in df.columns:
            return False
        return str(trade_id).strip() in df["trade_id"].astype(str).str.strip().values

    def upsert_trade(self, trade):
        if not isinstance(trade, dict):
            return {"saved": False, "reason": "Trade must be a dictionary"}
        trade_id = str(trade.get("trade_id", "")).strip()
        if not trade_id:
            return {"saved": False, "reason": "Missing trade_id"}

        row = {column: self._value(trade.get(column, "")) for column in self.TRADE_COLUMNS}
        try:
            df = pd.read_csv(self.trade_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            df = pd.DataFrame(columns=self.TRADE_COLUMNS)

        for column in self.TRADE_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        mask = (
            df["trade_id"].astype(str).str.strip() == trade_id
            if not df.empty else pd.Series(dtype=bool)
        )
        if not df.empty and bool(mask.any()):
            idx = df.index[mask][0]
            for column in self.TRADE_COLUMNS:
                new_value = row[column]
                if new_value != "" or column in self.EXIT_FIELDS:
                    df.at[idx, column] = new_value
        else:
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        df = df.reindex(columns=self.TRADE_COLUMNS)
        df.to_csv(self.trade_file, index=False)
        sync(self.trade_file, self.trade_file.replace(os.sep, "/"), f"Save paper trade {trade_id}")
        return {"saved": True, "trade_id": trade_id, "file": self.trade_file}

    def log_trade(self, trade):
        if not isinstance(trade, dict):
            return {"saved": False, "reason": "Trade must be a dictionary"}
        trade_id = str(trade.get("trade_id", "")).strip()
        if not trade_id:
            return {"saved": False, "reason": "Missing trade_id"}
        status = str(trade.get("status", "")).strip().upper()
        if status not in {"OPEN", "CLOSED"}:
            return {"saved": False, "reason": "Trade status must be OPEN or CLOSED"}
        return self.upsert_trade(trade)

    def log_signal(self, signal):
        if not isinstance(signal, dict):
            return {"saved": False, "reason": "Signal must be a dictionary"}
        if self.signal_exists(signal):
            return {"saved": False, "duplicate": True, "reason": "Duplicate scanner setup"}
        row = {column: self._value(signal.get(column, "")) for column in self.SIGNAL_COLUMNS}
        if not row["timestamp"]:
            row["timestamp"] = datetime.now().isoformat()
        with open(self.signal_file, "a", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=self.SIGNAL_COLUMNS).writerow(row)
        sync(self.signal_file, self.signal_file.replace(os.sep, "/"), "Save scanner signal")
        return {"saved": True, "duplicate": False, "file": self.signal_file}

    def get_trades(self):
        try:
            return pd.read_csv(self.trade_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame(columns=self.TRADE_COLUMNS)

    def get_signals(self):
        try:
            return pd.read_csv(self.signal_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame(columns=self.SIGNAL_COLUMNS)

    def summary(self):
        df = self.get_trades()
        if df.empty:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "breakeven_trades": 0, "win_rate": 0.0,
                "total_pnl": 0.0, "average_pnl": 0.0,
            }

        if "status" in df.columns:
            closed = df[df["status"].astype(str).str.upper() == "CLOSED"].copy()
        else:
            closed = df.copy()
        if closed.empty:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "breakeven_trades": 0, "win_rate": 0.0,
                "total_pnl": 0.0, "average_pnl": 0.0,
            }

        pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
        total = len(pnl)
        winning = int((pnl > 0).sum())
        losing = int((pnl < 0).sum())
        breakeven = int((pnl == 0).sum())
        return {
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": losing,
            "breakeven_trades": breakeven,
            "win_rate": round(winning / total * 100, 2) if total else 0.0,
            "total_pnl": round(float(pnl.sum()), 2),
            "average_pnl": round(float(pnl.mean()), 2),
        }
