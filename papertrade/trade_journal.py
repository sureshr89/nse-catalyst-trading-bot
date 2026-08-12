"""Trade and signal journal with optional GitHub-backed persistence."""

import csv
import os
from datetime import datetime

import pandas as pd

from config.settings import TRADE_LOG_FILE, SIGNAL_LOG_FILE
from papertrade.persistent_storage import restore, sync


class TradeJournal:
    TRADE_COLUMNS = [
        "trade_id", "symbol", "industry", "signal",
        "entry_time", "entry", "stop_loss", "target", "quantity",
        "exit_time", "exit_price", "exit_reason", "pnl",
        "risk_per_share", "actual_risk", "position_value",
        "breakout_level", "market_direction", "industry_direction",
        "stock_direction", "status",
    ]

    SIGNAL_COLUMNS = [
        "timestamp", "symbol", "industry", "signal",
        "market_direction", "industry_direction", "stock_direction",
        "breakout_level", "entry", "stop_loss", "target", "quantity",
        "approved", "reason",
    ]

    def __init__(self, trade_file=TRADE_LOG_FILE, signal_file=SIGNAL_LOG_FILE):
        self.trade_file = trade_file
        self.signal_file = signal_file
        self._prepare_files()
        # Restore the latest committed journal after a Streamlit restart.
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

    def log_trade(self, trade):
        if not isinstance(trade, dict):
            return {"saved": False, "reason": "Trade must be a dictionary"}
        trade_id = str(trade.get("trade_id", "")).strip()
        if not trade_id:
            return {"saved": False, "reason": "Missing trade_id"}
        status = str(trade.get("status", "")).strip().upper()
        if status != "CLOSED":
            return {"saved": False, "reason": "Only CLOSED trades can be saved"}
        if self.trade_exists(trade_id):
            return {"saved": False, "reason": f"{trade_id} already exists"}

        row = {column: self._value(trade.get(column, "")) for column in self.TRADE_COLUMNS}
        with open(self.trade_file, "a", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=self.TRADE_COLUMNS).writerow(row)

        sync(self.trade_file, self.trade_file.replace(os.sep, "/"), f"Save paper trade {trade_id}")
        return {"saved": True, "trade_id": trade_id, "file": self.trade_file}

    def log_signal(self, signal):
        if not isinstance(signal, dict):
            return {"saved": False, "reason": "Signal must be a dictionary"}
        row = {column: self._value(signal.get(column, "")) for column in self.SIGNAL_COLUMNS}
        if not row["timestamp"]:
            row["timestamp"] = datetime.now().isoformat()
        with open(self.signal_file, "a", newline="", encoding="utf-8") as file:
            csv.DictWriter(file, fieldnames=self.SIGNAL_COLUMNS).writerow(row)
        sync(self.signal_file, self.signal_file.replace(os.sep, "/"), "Save scanner signal")
        return {"saved": True, "file": self.signal_file}

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
        pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
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
