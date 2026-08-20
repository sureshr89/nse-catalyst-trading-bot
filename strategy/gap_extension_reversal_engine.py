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
        self.start_time = start_time
        self.end_time = end_time
        self.rr = float(rr)

    @staticmethod
    def _completed(data, as_of=None):
        if data is None or data.empty or "Datetime" not in data.columns:
            return pd.DataFrame()
        rows = data.copy()
        rows["Datetime"] = pd.to_datetime(rows["Datetime"], errors="coerce")
        rows = rows.dropna(subset=["Datetime"]).sort_values("Datetime")
        if rows.empty:
            return rows
        first = rows["Datetime"].iloc[0]
        if getattr(first, "tzinfo", None) is not None:
            cutoff = as_of or datetime.now(first.tzinfo)
        else:
            cutoff = as_of or datetime.now()
        if getattr(cutoff, "tzinfo", None) is None and getattr(first, "tzinfo", None) is not None:
            cutoff = cutoff.replace(tzinfo=first.tzinfo)
        cutoff = cutoff.replace(second=0, microsecond=0)
        return rows[rows["Datetime"] < cutoff].copy().reset_index(drop=True)

    def _live(self, symbol):
        try:
            return _LIVE.get_latest_live_price(symbol, max_age_seconds=2) or {}
        except Exception:
            return {}

    def evaluate(self, symbol, data, pdh, pdl, pdc, nifty_change_pct, previous_close=None, as_of=None):
        history = self._completed(data, as_of=as_of)
        # Strategy 2 needs enough completed history to establish an extension,
        # while the actual entry remains the live LTP.
        if len(history) < 3:
            return None

        open_price = float(data.iloc[0]["Open"])
        pdh = float(pdh)
        pdc = float(pdc)
        pdl = float(pdl) if pdl is not None else None
        nifty = float(nifty_change_pct or 0)
        live = self._live(symbol)
        try:
            entry = float(live.get("Close"))
            live_high = float(live.get("High", entry))
            live_low = float(live.get("Low", entry))
        except (TypeError, ValueError):
            return None
        if entry <= 0:
            return None

        historical_high = pd.to_numeric(history["High"], errors="coerce").dropna()
        historical_low = pd.to_numeric(history["Low"], errors="coerce").dropna()

        # GAP-UP extension reversal: Open > PDH, price extends above Open,
        # then live LTP reverses below Open. Target is PDC.
        if open_price > pdh and pdc < open_price:
            day_high = max([open_price] + historical_high.tolist() + [live_high])
            if day_high > open_price and entry < open_price and nifty <= 0.25:
                stop = day_high
                target = pdc
                if target < entry < stop:
                    return {
                        "strategy": self.strategy_id,
                        "strategy_version": self.strategy_version,
                        "strategy_id": self.strategy_id,
                        "symbol": symbol,
                        "signal": "SELL",
                        "entry": entry,
                        "target": target,
                        "stop_loss": stop,
                        "entry_source": "LIVE_LTP",
                    }

        # GAP-DOWN extension reversal: Open < PDL, price extends below Open,
        # then live LTP reclaims above Open. Target is PDC.
        if pdl is not None and open_price < pdl and pdc > open_price:
            day_low = min([open_price] + historical_low.tolist() + [live_low])
            if day_low < open_price and entry > open_price and nifty >= -0.25:
                stop = day_low
                target = pdc
                if stop < entry < target:
                    return {
                        "strategy": self.strategy_id,
                        "strategy_version": self.strategy_version,
                        "strategy_id": self.strategy_id,
                        "symbol": symbol,
                        "signal": "BUY",
                        "entry": entry,
                        "target": target,
                        "stop_loss": stop,
                        "entry_source": "LIVE_LTP",
                    }
        return None

    def initial_side(self, *args, **kwargs):
        try:
            o, pdh, pdl = args[:3]
            if float(o) > float(pdh):
                return "SELL"
            if float(o) < float(pdl):
                return "BUY"
        except Exception:
            pass
        return None
