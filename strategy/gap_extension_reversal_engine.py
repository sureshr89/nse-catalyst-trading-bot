from __future__ import annotations

from strategy.contracts import STRATEGY_VERSION

try:
    from market.live_price import LIVE as _LIVE
except Exception:
    class _FallbackLive:
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {}
    _LIVE = _FallbackLive()


class GapExtensionReversalEngine:
    strategy_id = "STRATEGY_2"
    strategy_version = STRATEGY_VERSION

    def __init__(self, start_time="09:45", end_time="14:00", rr=1.25):
        self.start_time = start_time
        self.end_time = end_time
        self.rr = float(rr)

    def evaluate(self, symbol, data, pdh, pdl, pdc, nifty_change_pct, previous_close, as_of=None):
        if data is None or len(data) < 2:
            return None
        rows = data.copy().sort_values("Datetime")
        open_price = float(rows.iloc[0]["Open"])
        day_high = float(rows["High"].max())
        day_low = float(rows["Low"].min())
        live = _LIVE.get_latest_live_price(symbol, max_age_seconds=2) or {}
        entry = float(live.get("Close") or 0)
        if entry <= 0:
            return None
        nifty = float(nifty_change_pct or 0)
        last_close = float(rows.iloc[-1]["Close"])
        if open_price > float(pdh) and nifty <= 0.2 and last_close < float(pdh):
            stop = day_high; target = float(pdc)
            if target < entry < stop:
                return {"strategy":"STRATEGY_2","strategy_version":self.strategy_version,"strategy_id":self.strategy_id,"symbol":symbol,"signal":"SELL","entry":entry,"target":target,"stop_loss":stop,"entry_source":"LIVE_LTP"}
        if open_price < float(pdl) and nifty >= -0.2 and last_close > open_price:
            stop = day_low; target = float(pdc)
            if stop < entry < target:
                return {"strategy":"STRATEGY_2","strategy_version":self.strategy_version,"strategy_id":self.strategy_id,"symbol":symbol,"signal":"BUY","entry":entry,"target":target,"stop_loss":stop,"entry_source":"LIVE_LTP"}
        return None

    def initial_side(self, *args, **kwargs):
        return None
