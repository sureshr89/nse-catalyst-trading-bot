"""Track strategy-qualified paper trades that were missed only because of capital."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import TRADE_LOG_FILE


class MissedCapitalTracker:
    """Persist and resolve hypothetical outcomes for capital-blocked trades."""

    def __init__(self, journal, price_data):
        self.journal = journal
        self.price_data = price_data

    @staticmethod
    def _number(value):
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None

    def record(self, signal, risk_result, reason):
        symbol = str(signal.get("symbol", "")).strip().upper()
        if not symbol:
            return
        entry = self._number(signal.get("entry"))
        stop = self._number(signal.get("stop_loss"))
        target = self._number(signal.get("target"))
        quantity = self._number(risk_result.get("quantity"))
        if entry is None or stop is None or target is None or quantity is None or quantity <= 0:
            return
        entry_time = signal.get("entry_time") or datetime.now().astimezone().isoformat()
        trade_id = "MISSED-CAPITAL-{}-{}".format(
            str(entry_time).replace("+", "p").replace(":", "").replace("-", "")[:19],
            symbol,
        )
        existing = self.journal.get_trades()
        if not existing.empty and "trade_id" in existing.columns:
            if trade_id in existing["trade_id"].astype(str).values:
                return
        row = dict(signal)
        row.update({
            "trade_id": trade_id,
            "symbol": symbol,
            "stock": symbol,
            "entry_time": entry_time,
            "entry": entry,
            "stop_loss": stop,
            "target": target,
            "quantity": int(quantity),
            "risk": self._number(risk_result.get("actual_risk")) or 0.0,
            "reward": self._number(risk_result.get("reward")) or 0.0,
            "rr": self._number(risk_result.get("rr")) or 0.0,
            "risk_per_share": self._number(risk_result.get("risk_per_share")) or abs(entry - stop),
            "actual_risk": self._number(risk_result.get("actual_risk")) or 0.0,
            "position_value": self._number(risk_result.get("position_value")) or entry * int(quantity),
            "status": "MISSED_CAPITAL_OPEN",
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "pnl": None,
            "setup_type": signal.get("setup_type", ""),
        })
        row["exit_reason"] = f"MISSED_CAPITAL: {reason}"
        self.journal.upsert_trade(row)

    def _open_rows(self):
        df = self.journal.get_trades()
        if df.empty or "status" not in df.columns:
            return pd.DataFrame()
        return df[df["status"].astype(str).str.upper() == "MISSED_CAPITAL_OPEN"].copy()

    def monitor(self):
        rows = self._open_rows()
        if rows.empty:
            return
        for _, trade in rows.iterrows():
            symbol = str(trade.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            try:
                candles = self.price_data.get_1m(symbol)
            except Exception:
                continue
            if candles is None or candles.empty:
                continue
            try:
                candles = self.price_data.today_only(candles)
            except Exception:
                pass
            if candles is None or candles.empty:
                continue
            candle = candles.iloc[-1]
            entry = self._number(trade.get("entry"))
            stop = self._number(trade.get("stop_loss"))
            target = self._number(trade.get("target"))
            quantity = self._number(trade.get("quantity"))
            if None in (entry, stop, target, quantity) or quantity <= 0:
                continue
            high = self._number(candle.get("High"))
            low = self._number(candle.get("Low"))
            close = self._number(candle.get("Close"))
            if None in (high, low, close):
                continue
            side = str(trade.get("signal", "")).upper()
            reason = None
            exit_price = None
            if side == "BUY":
                if low <= stop:
                    reason, exit_price = "MISSED_CAPITAL_STOP_LOSS", stop
                elif high >= target:
                    reason, exit_price = "MISSED_CAPITAL_TARGET", target
            elif side == "SELL":
                if high >= stop:
                    reason, exit_price = "MISSED_CAPITAL_STOP_LOSS", stop
                elif low <= target:
                    reason, exit_price = "MISSED_CAPITAL_TARGET", target
            if reason is None:
                continue
            pnl = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
            updated = trade.to_dict()
            updated.update({
                "status": "MISSED_CAPITAL_CLOSED",
                "exit_time": candle.get("Datetime", datetime.now().astimezone().isoformat()),
                "exit_price": round(exit_price, 4),
                "exit_reason": reason,
                "pnl": round(pnl, 2),
            })
            self.journal.upsert_trade(updated)
