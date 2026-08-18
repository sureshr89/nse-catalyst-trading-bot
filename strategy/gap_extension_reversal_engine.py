"""Strategy 2: gap extension reversal, BUY and SELL."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from strategy.contracts import STRATEGY_VERSION, STRATEGY_2_NAME

INDIA_TZ = ZoneInfo("Asia/Kolkata")
NIFTY_BLOCK_PCT = 0.25


class GapExtensionReversalEngine:
    """Gap extension reversal using completed 1-minute candles only."""

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

    def _base(self, symbol, side, entry, open_price, pdc, pdh, pdl, stop, target, candle, nifty):
        risk = (stop - entry) if side == "SELL" else (entry - stop)
        reward = (entry - target) if side == "SELL" else (target - entry)
        if risk <= 0 or reward <= 0:
            return None
        rr = reward / risk
        if rr < self.rr:
            return None
        gap = (open_price - pdc) / pdc * 100 if pdc else 0.0
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
            "setup_type": "GAP_UP_EXTENSION_REVERSAL_SELL" if side == "SELL" else "GAP_DOWN_EXTENSION_REVERSAL_BUY",
            "trigger_close": round(entry, 4),
            "trigger_time": candle["Datetime"].isoformat(),
            "nifty500_change_pct": round(float(nifty), 4),
        }

    def evaluate(self, symbol, today_data, today_open, pdh, pdc, nifty_change_pct, pdl=None, as_of=None):
        data = self._completed(today_data, as_of=as_of)
        if data is None or data.empty:
            return None
        open_price, pdh, pdc = float(today_open), float(pdh), float(pdc)
        pdl = float(pdl) if pdl is not None else None
        session_date = data["Datetime"].dt.date.max()
        today = data[data["Datetime"].dt.date == session_date].copy()
        if today.empty:
            return None
        candles = today[(today["Datetime"].dt.time >= self.start) & (today["Datetime"].dt.time <= self.end)].copy()
        if candles.empty:
            return None

        if open_price > pdh and pdc < open_price:
            extended = False
            day_high = open_price
            for _, candle in candles.iterrows():
                high, close = float(candle["High"]), float(candle["Close"])
                day_high = max(day_high, high)
                if high > open_price:
                    extended = True
                if extended and close < open_price:
                    if float(nifty_change_pct) > NIFTY_BLOCK_PCT:
                        return None
                    # First completed trigger is authoritative; do not replace it
                    # with a later reversal candle.
                    return self._base(symbol, "SELL", close, open_price, pdc, pdh, pdl, day_high, pdh, candle, nifty_change_pct)
            return None

        if pdl is not None and open_price < pdl and pdc > open_price:
            extended = False
            day_low = open_price
            for _, candle in candles.iterrows():
                low, close = float(candle["Low"]), float(candle["Close"])
                day_low = min(day_low, low)
                if low < open_price:
                    extended = True
                if extended and close > open_price:
                    if float(nifty_change_pct) < -NIFTY_BLOCK_PCT:
                        return None
                    # First completed trigger is authoritative; do not replace it
                    # with a later reversal candle.
                    return self._base(symbol, "BUY", close, open_price, pdc, pdh, pdl, day_low, pdl, candle, nifty_change_pct)
            return None
        return None
