"""Track strategy-qualified trades missed only because of capital."""

from datetime import datetime

import pandas as pd

from config.settings import SQUARE_OFF_TIME


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

    @staticmethod
    def _hhmm(value):
        if value is None:
            return None
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.strftime("%H:%M")
        except Exception:
            return None

    @staticmethod
    def _timestamp(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            return None if pd.isna(parsed) else parsed
        except Exception:
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
        if not existing.empty and "trade_id" in existing.columns and trade_id in existing["trade_id"].astype(str).values:
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
            "exit_reason": f"MISSED_CAPITAL: {reason}",
            "pnl": None,
            "setup_type": signal.get("setup_type", ""),
        })
        self.journal.upsert_trade(row)

    def _open_rows(self):
        df = self.journal.get_trades()
        if df.empty or "status" not in df.columns:
            return pd.DataFrame()
        return df[df["status"].astype(str).str.upper() == "MISSED_CAPITAL_OPEN"].copy()

    def _close_from_candles(self, trade, candles):
        if candles is None or candles.empty:
            return None
        frame = candles.copy()
        if "Datetime" not in frame.columns:
            return None
        frame["Datetime"] = pd.to_datetime(frame["Datetime"], errors="coerce")
        frame = frame.dropna(subset=["Datetime"]).sort_values("Datetime")
        entry_time = self._timestamp(trade.get("entry_time"))
        if entry_time is not None:
            frame = frame[frame["Datetime"] > entry_time]
        if frame.empty:
            return None

        entry = self._number(trade.get("entry"))
        stop = self._number(trade.get("stop_loss"))
        target = self._number(trade.get("target"))
        quantity = self._number(trade.get("quantity"))
        if None in (entry, stop, target, quantity) or quantity <= 0:
            return None

        side = str(trade.get("signal", "")).upper()
        for _, candle in frame.iterrows():
            high = self._number(candle.get("High"))
            low = self._number(candle.get("Low"))
            close = self._number(candle.get("Close"))
            if None in (high, low, close):
                continue
            candle_time = candle.get("Datetime")
            reason = None
            exit_price = None

            if side == "BUY":
                sl_hit, target_hit = low <= stop, high >= target
            elif side == "SELL":
                sl_hit, target_hit = high >= stop, low <= target
            else:
                continue

            # OHLC cannot reveal intrabar order. Keep the same conservative
            # stop-first rule used by the real paper execution engine.
            if sl_hit:
                reason, exit_price = "MISSED_CAPITAL_STOP_LOSS", stop
            elif target_hit:
                reason, exit_price = "MISSED_CAPITAL_TARGET", target
            elif self._hhmm(candle_time) and self._hhmm(candle_time) >= SQUARE_OFF_TIME:
                reason, exit_price = "MISSED_CAPITAL_SQUARE_OFF", close

            if reason is None:
                continue

            pnl = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
            return {
                "status": "MISSED_CAPITAL_CLOSED",
                "exit_time": candle_time,
                "exit_price": round(exit_price, 4),
                "exit_reason": reason,
                "pnl": round(pnl, 2),
            }
        return None

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
                candles = self.price_data.today_only(candles)
            except Exception:
                continue
            if candles is None or candles.empty:
                continue

            outcome = self._close_from_candles(trade, candles)
            if outcome is None:
                continue
            updated = trade.to_dict()
            updated.update(outcome)
            self.journal.upsert_trade(updated)
            print("MISSED CAPITAL CLOSED:", symbol, outcome["exit_reason"], "P&L=", outcome["pnl"])
