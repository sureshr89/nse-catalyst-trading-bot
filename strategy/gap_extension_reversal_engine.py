"""Strategy 2: gap-up extension reversal SELL.

Rules:
- Today's Open > PDH.
- Opening gap from Previous Day Close is used for priority.
- No entry before 09:45 IST.
- Stock must first move above Today's Open after 09:45.
- First completed 1-minute CLOSE below Today's Open triggers SELL.
- Stop = Today's High at entry.
- Target = PDH.
- NIFTY alignment is intentionally soft: SELL is allowed when NIFTY 500 is not bullish.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo("Asia/Kolkata")


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
        result["Datetime"] = __import__("pandas").to_datetime(result["Datetime"], errors="coerce")
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
        # The stock must actually extend upward after the entry window begins.
        after_start = today[today["Datetime"].dt.time >= self.start]
        if after_start.empty:
            return None
        extension = after_start[after_start["High"].astype(float) > open_price]
        if extension.empty:
            return None
        high_to_entry = float(extension["High"].max())
        for _, candle in after_start.iterrows():
            close = float(candle["Close"])
            if close < open_price:
                stop = high_to_entry
                risk = stop - close
                reward = close - pdh
                if risk <= 0 or reward <= 0:
                    continue
                rr = reward / risk
                if rr < self.rr:
                    continue
                # Soft market filter: do not short into a clearly bullish NIFTY 500.
                if float(nifty_change_pct) > 0:
                    continue
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
