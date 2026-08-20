from __future__ import annotations

from datetime import datetime
from strategy.contracts import STRATEGY_VERSION


class OpenReversalEngine:
    strategy_id = "STRATEGY_1"
    strategy_version = STRATEGY_VERSION

    def __init__(self, start_time="09:45", end_time="14:00", rr=1.25):
        self.start_time = start_time
        self.end_time = end_time
        self.rr = float(rr)

    def latest_completed(self, data):
        if data is None or len(data) < 1:
            return None
        x = data.copy()
        x["Datetime"] = __import__("pandas").to_datetime(x["Datetime"])
        now = datetime.now(x["Datetime"].iloc[0].tzinfo) if getattr(x["Datetime"].iloc[0], "tzinfo", None) else datetime.now()
        completed = x[x["Datetime"] < now]
        return completed.iloc[-1] if not completed.empty else x.iloc[-1]

    def build_signal(self, symbol, side, entry, reference, open_price, stop_reference, nifty_change_pct):
        entry = float(entry); stop_reference = float(stop_reference)
        if side == "BUY":
            stop = stop_reference
            target = entry + (entry - stop) * self.rr
        else:
            stop = stop_reference
            target = entry - (stop - entry) * self.rr
        return {
            "strategy": self.strategy_id, "strategy_version": self.strategy_version,
            "symbol": symbol, "signal": side, "entry": entry,
            "stop_loss": stop, "target": target, "risk_reward": self.rr,
            "entry_source": "LIVE_LTP",
        }

    def update_state(self, state, pdh, pdl, open_price, price):
        side = state.get("side")
        if side == "BUY":
            if price < open_price:
                state["pdh_breached"] = True
            if state.get("pdh_breached") and price >= pdh:
                state["open_returned"] = True
        elif side == "SELL":
            if price > open_price:
                state["pdl_breached"] = True
            if state.get("pdl_breached") and price <= pdl:
                state["open_returned"] = True
        return state

    def build(self, symbol, data, pdh, pdl, today_open, nifty_change_pct=0.0):
        if data is None or len(data) < 2:
            return None
        row = self.latest_completed(data)
        if row is None:
            return None
        close = float(row["Close"])
        side = "BUY" if close > today_open else "SELL" if close < today_open else None
        if side is None:
            return None
        return None

    def initial_side(self, *args, **kwargs):
        return None
