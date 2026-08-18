"""Strategy 2: gap extension reversal BUY and SELL using live LTP triggers."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from strategy.contracts import STRATEGY_VERSION, STRATEGY_2_NAME
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
NIFTY_BLOCK_PCT = 0.25
_LIVE = PriceData()


class GapExtensionReversalEngine:
    """Gap extension reversal. Entry is triggered by live LTP, never candle close."""

    strategy_id = "STRATEGY_2"
    strategy_name = STRATEGY_2_NAME
    strategy_version = STRATEGY_VERSION

    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.25):
        self.start = self._time(trading_start)
        self.end = self._time(last_entry_time)
        self.rr = float(rr)

    @staticmethod
    def _time(value):
        h, m = map(int, str(value).split(":"))
        return time(h, m)

    @staticmethod
    def _completed(data, as_of=None):
        if data is None or data.empty or "Datetime" not in data.columns:
            return data
        result = data.copy()
        result["Datetime"] = pd.to_datetime(result["Datetime"], errors="coerce")
        result = result.dropna(subset=["Datetime"])
        if result.empty:
            return result
        if result["Datetime"].dt.tz is None:
            result["Datetime"] = result["Datetime"].dt.tz_localize(INDIA_TZ)
        else:
            result["Datetime"] = result["Datetime"].dt.tz_convert(INDIA_TZ)
        cutoff = as_of or datetime.now(INDIA_TZ)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=INDIA_TZ)
        cutoff = cutoff.astimezone(INDIA_TZ).replace(second=0, microsecond=0)
        return result[result["Datetime"] < cutoff].copy().sort_values("Datetime").reset_index(drop=True)

    @staticmethod
    def _live(symbol):
        try:
            return _LIVE.get_latest_live_price(str(symbol), max_age_seconds=2)
        except Exception:
            return None

    def _base(self, symbol, side, entry, open_price, pdc, pdh, pdl, stop, target, trigger_time, nifty):
        risk = (stop - entry) if side == "SELL" else (entry - stop)
        reward = (entry - target) if side == "SELL" else (target - entry)
        if risk <= 0 or reward <= 0:
            return None
        rr = reward / risk
        if rr < self.rr:
            return None
        gap = (open_price - pdc) / pdc * 100 if pdc else 0.0
        now = datetime.now(INDIA_TZ)
        return {
            "symbol": str(symbol).upper(),
            "strategy": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "signal": side,
            "entry": round(entry, 4),
            "today_open": round(open_price, 4),
            "previous_day_close": round(pdc, 4),
            "pdh": round(pdh, 4),
            "pdl": round(pdl, 4),
            "today_high": round(stop, 4) if side == "SELL" else None,
            "today_low": round(stop, 4) if side == "BUY" else None,
            "stop_loss": round(stop, 4),
            "target": round(target, 4),
            "risk_reward": round(rr, 4),
            "gap_percent": round(gap, 4),
            "gap_type": "GAP_UP_EXTENSION_REVERSAL" if side == "SELL" else "GAP_DOWN_EXTENSION_REVERSAL",
            "setup_type": "GAP_UP_EXTENSION_REVERSAL_SELL_LIVE_LTP" if side == "SELL" else "GAP_DOWN_EXTENSION_REVERSAL_BUY_LIVE_LTP",
            "trigger_close": round(entry, 4),
            "trigger_price": round(entry, 4),
            "trigger_time": now.isoformat(timespec="milliseconds"),
            "entry_time": now.isoformat(timespec="milliseconds"),
            "trigger_entry_time": now.isoformat(timespec="milliseconds"),
            "market_entry_time": now.isoformat(timespec="milliseconds"),
            "nifty500_change_pct": round(float(nifty), 4),
            "entry_source": "LIVE_LTP",
        }

    def evaluate(self, symbol, today_data, today_open, pdh, pdc, nifty_change_pct, pdl=None, as_of=None):
        """Use completed history only for recovery; trigger the actual entry from live LTP."""
        history = self._completed(today_data, as_of=as_of)
        if history is None or history.empty:
            return None
        open_price, pdh, pdc = float(today_open), float(pdh), float(pdc)
        pdl = float(pdl) if pdl is not None else None
        session_date = history["Datetime"].dt.date.max()
        today = history[history["Datetime"].dt.date == session_date].copy()
        if today.empty:
            return None
        now_time = datetime.now(INDIA_TZ).time()
        if not (self.start <= now_time <= self.end):
            return None
        live = self._live(symbol)
        if live is None:
            return None
        try:
            ltp = float(live.get("Close"))
            live_high = float(live.get("High")) if live.get("High") is not None else ltp
            live_low = float(live.get("Low")) if live.get("Low") is not None else ltp
        except (TypeError, ValueError):
            return None

        if open_price > pdh and pdc < open_price:
            historical_high = pd.to_numeric(today["High"], errors="coerce").dropna()
            day_high = max([open_price] + historical_high.tolist()) if not historical_high.empty else open_price
            extended = day_high > open_price
            # Current bar can establish extension and immediately reverse below open.
            extended = extended or live_high > open_price
            if extended and ltp < open_price:
                if float(nifty_change_pct) > NIFTY_BLOCK_PCT:
                    return None
                day_high = max(day_high, live_high)
                return self._base(symbol, "SELL", ltp, open_price, pdc, pdh, pdl, day_high, pdh, now_time, nifty_change_pct)
            return None

        if pdl is not None and open_price < pdl and pdc > open_price:
            historical_low = pd.to_numeric(today["Low"], errors="coerce").dropna()
            day_low = min([open_price] + historical_low.tolist()) if not historical_low.empty else open_price
            extended = day_low < open_price
            extended = extended or live_low < open_price
            if extended and ltp > open_price:
                if float(nifty_change_pct) < -NIFTY_BLOCK_PCT:
                    return None
                day_low = min(day_low, live_low)
                return self._base(symbol, "BUY", ltp, open_price, pdc, pdh, pdl, day_low, pdl, now_time, nifty_change_pct)
            return None
        return None
