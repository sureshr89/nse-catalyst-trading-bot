from __future__ import annotations
from datetime import datetime
import pandas as pd
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
        self.start_time, self.end_time, self.rr = start_time, end_time, float(rr)

    @staticmethod
    def _completed(data, as_of=None):
        if data is None or data.empty or "Datetime" not in data.columns: return pd.DataFrame()
        rows = data.copy()
        rows["Datetime"] = pd.to_datetime(rows["Datetime"], errors="coerce")
        rows = rows.dropna(subset=["Datetime"]).sort_values("Datetime")
        if rows.empty: return rows
        first = rows["Datetime"].iloc[0]
        cutoff = as_of or datetime.now(first.tzinfo if getattr(first, "tzinfo", None) else None)
        if getattr(cutoff, "tzinfo", None) is None and getattr(first, "tzinfo", None) is not None:
            cutoff = cutoff.replace(tzinfo=first.tzinfo)
        cutoff = cutoff.replace(second=0, microsecond=0)
        return rows[rows["Datetime"] < cutoff].copy().reset_index(drop=True)

    def _live(self, symbol):
        try: return _LIVE.get_latest_live_price(symbol, max_age_seconds=2) or {}
        except Exception: return {}

    @staticmethod
    def _result(symbol, signal, entry, target, stop):
        return {"strategy":"STRATEGY_2", "strategy_version":STRATEGY_VERSION, "strategy_id":"STRATEGY_2",
                "symbol":symbol, "signal":signal, "entry":float(entry), "target":float(target),
                "stop_loss":float(stop), "entry_source":"LIVE_LTP"}

    def evaluate(self, symbol, data, pdh, pdl, pdc, nifty_change_pct, previous_close=None, as_of=None):
        history = self._completed(data, as_of=as_of)
        if len(history) < 3: return None
        open_price = float(data.iloc[0]["Open"])
        pdh = float(pdh); pdc = float(pdc); pdl = float(pdl) if pdl is not None else None
        nifty = float(nifty_change_pct or 0)
        live = self._live(symbol)
        try: entry = float(live["Close"])
        except (KeyError, TypeError, ValueError): return None
        if entry <= 0: return None
        highs = pd.to_numeric(history["High"], errors="coerce").dropna().tolist()
        lows = pd.to_numeric(history["Low"], errors="coerce").dropna().tolist()
        if not highs or not lows: return None
        trigger_high = max(highs); trigger_low = min(lows)

        # Sell mirror: open must be above PDH, price must extend to/above the
        # opening price, then live LTP reverses below the open. PDC is target.
        if open_price > pdh and pdc < open_price and trigger_high >= open_price:
            if entry < open_price and nifty <= 0.25 and pdc < entry < trigger_high:
                return self._result(symbol, "SELL", entry, pdc, trigger_high)

        # Buy mirror: open must be below PDL but above PDH (inside the prior-day
        # gap/range represented by PDH < Open < PDL), then extend below open,
        # followed by a live reclaim. PDC is target.
        if pdl is not None and open_price > pdh and open_price < pdl and pdc > open_price and trigger_low < open_price:
            if entry > open_price and nifty >= -0.25 and trigger_low < entry < pdc:
                return self._result(symbol, "BUY", entry, pdc, trigger_low)
        return None

    def initial_side(self, *args, **kwargs):
        try:
            o, pdh, pdl = args[:3]
            if float(o) > float(pdh): return "SELL"
            if float(o) < float(pdl): return "BUY"
        except Exception: pass
        return None
