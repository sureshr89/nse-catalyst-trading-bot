"""Strategy 2: gap-up extension reversal SELL.

Rules:
- Today's Open > PDH.
- Opening gap from Previous Day Close is used for priority.
- No entry before 09:45 IST.
- Stock must first move above Today's Open after 09:45.
- The first completed 1-minute CLOSE below Today's Open is the only entry trigger.
- Stop = Today's High at the trigger candle.
- Target = PDH.
- NIFTY 500 is a soft protective filter: only clearly bullish (> +0.25%) blocks the short.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd

INDIA_TZ = ZoneInfo("Asia/Kolkata")
NIFTY_BULLISH_BLOCK_PCT = 0.25


class GapExtensionReversalEngine:
    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.25):
        self.start = self._time(trading_start)
        self.end = self._time(last_entry_time)
        self.rr = float(rr)

    @staticmethod
    def _time(value):
        h, m = map(int, str(value).split(":"))
        return time(h, m)

    @staticmethod
    def _completed(data):
        if data is None or data.empty or "Datetime" not in data.columns:
            return data
        result = data.copy()
        result["Datetime"] = pd.to_datetime(result["Datetime"], errors="coerce")
        result = result.dropna(subset=["Datetime"])
        if result["Datetime"].dt.tz is None:
            result["Datetime"] = result["Datetime"].dt.tz_localize(INDIA_TZ)
        else:
            result["Datetime"] = result["Datetime"].dt.tz_convert(INDIA_TZ)
        now = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        return result[result["Datetime"] < now].copy()

    def evaluate(self, symbol, today_data, today_open, pdh, pdc, nifty_change_pct):
        data = self._completed(today_data)
        if data is None or data.empty:
            return None
        open_price = float(today_open)
        pdh = float(pdh)
        pdc = float(pdc)
        if not (open_price > pdh and pdc < open_price):
            return None
        today = data[data["Datetime"].dt.date == datetime.now(INDIA_TZ).date()].copy()
        if today.empty:
            return None
        after_start = today[
            (today["Datetime"].dt.time >= self.start)
            & (today["Datetime"].dt.time <= self.end)
        ].copy()
        if after_start.empty:
            return None

        extended = False
        day_high = open_price
        for _, candle in after_start.iterrows():
            high = float(candle["High"])
            close = float(candle["Close"])
            day_high = max(day_high, high)
            if high > open_price:
                extended = True
                continue
            if not extended:
                continue
            if close >= open_price:
                continue

            # This is the first completed close below Today's Open. It is the
            # only reversal trigger for the setup; later candles are ignored.
            stop = day_high
            risk = stop - close
            reward = close - pdh
            if risk <= 0 or reward <= 0:
                return None
            rr = reward / risk
            if rr < self.rr:
                return None
            # Keep the same practical market-alignment threshold as Strategy 1:
            # a clearly bullish NIFTY 500 blocks a short, but small positive
            # movement does not.
            if float(nifty_change_pct) > NIFTY_BULLISH_BLOCK_PCT:
                return None
            return {
                "symbol": str(symbol).upper(),
                "signal": "SELL",
                "entry": round(close, 4),
                "today_open": round(open_price, 4),
                "previous_day_close": round(pdc, 4),
                "pdh": round(pdh, 4),
                "pdl": None,
                "today_high": round(stop, 4),
                "stop_loss": round(stop, 4),
                "target": round(pdh, 4),
                "risk_reward": round(rr, 4),
                "gap_percent": round((open_price - pdc) / pdc * 100, 4) if pdc else 0.0,
                "gap_type": "GAP_UP_EXTENSION_REVERSAL",
                "setup_type": "GAP_UP_EXTENSION_REVERSAL_SELL",
                "trigger_close": round(close, 4),
                "trigger_time": candle["Datetime"].isoformat(),
                "nifty500_change_pct": round(float(nifty_change_pct), 4),
            }
        return None
