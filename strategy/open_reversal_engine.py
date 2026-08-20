from __future__ import annotations
from datetime import datetime
from strategy.contracts import STRATEGY_VERSION
try:
    from market.live_price import LIVE as _LIVE
except Exception:
    class _FallbackLive:
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {}
    _LIVE = _FallbackLive()

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
        import pandas as pd
        x = data.copy()
        x["Datetime"] = pd.to_datetime(x["Datetime"], errors="coerce")
        x = x.dropna(subset=["Datetime"]).sort_values("Datetime")
        if x.empty:
            return None
        first = x["Datetime"].iloc[0]
        if getattr(first, "tzinfo", None) is not None:
            now = datetime.now(first.tzinfo).replace(second=0, microsecond=0)
        else:
            now = datetime.now().replace(second=0, microsecond=0)
        completed = x[x["Datetime"] < now]
        return None if completed.empty else completed.iloc[-1]

    def build_signal(self, symbol, side, entry, reference, open_price, stop_reference, nifty_change_pct):
        entry = float(entry)
        side = str(side).upper()
        # Compatibility contract: S1 BUY uses the supplied PDH/reference level
        # carried as open_price; SELL uses the explicit stop reference.
        stop = float(open_price) if side == "BUY" else float(stop_reference)
        if stop <= 0:
            return None
        if side == "BUY":
            if stop >= entry:
                return None
            target = entry + (entry - stop) * self.rr
        elif side == "SELL":
            if stop <= entry:
                return None
            target = entry - (stop - entry) * self.rr
        else:
            return None
        return {
            "strategy": self.strategy_id,
            "strategy_version": self.strategy_version,
            "symbol": symbol,
            "signal": side,
            "entry": entry,
            "stop_loss": stop,
            "target": target,
            "risk_reward": self.rr,
            "entry_source": "LIVE_LTP",
        }

    def update_state(self, state, open_price, pdh, pdl, price=None):
        """Track S1 as: breach the prior-day level, then return to today's open."""
        state = dict(state)
        live = _LIVE.get_latest_live_price(state.get("symbol", ""), max_age_seconds=2) or {}
        if live:
            price = live.get("Close")
        if price is None:
            return state
        try:
            price = float(price)
            open_price = float(open_price)
            pdh = float(pdh)
            pdl = float(pdl)
        except (TypeError, ValueError):
            return state
        side = str(state.get("side", "")).upper()
        if side == "BUY":
            # Open is above PDH: first touch below PDH, then reclaim Open.
            if price <= pdh:
                state["pdh_breached"] = True
            if state.get("pdh_breached") and price >= open_price:
                state["open_returned"] = True
        elif side == "SELL":
            # Open is below PDL: first touch above PDL, then reject back through Open.
            if price >= pdl:
                state["pdl_breached"] = True
            if state.get("pdl_breached") and price <= open_price:
                state["open_returned"] = True
        return state

    def build(self, *args, **kwargs):
        return None

    def initial_side(self, *args, **kwargs):
        try:
            o, pdh, pdl = args[:3]
            if float(o) > float(pdh):
                return "BUY"
            if float(o) < float(pdl):
                return "SELL"
        except Exception:
            pass
        return None
