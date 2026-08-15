"""NIFTY 500 PDH/PDL + Today's Open 1-minute reversal strategy."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import ENABLE_LONG, ENABLE_SHORT, MAX_TRIGGER_AGE_MINUTES

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class OpenReversalEngine:
    """Generate only fresh 1-minute price-action reversal entries."""

    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.25):
        self.start = self._time(trading_start)
        self.end = self._time(last_entry_time)
        self.rr = float(rr)
        self._finalized_triggers = {}

    @staticmethod
    def _time(value):
        h, m = map(int, str(value).split(":"))
        return time(h, m)

    @staticmethod
    def _clean_prices(data):
        required = {"Datetime", "Open", "High", "Low", "Close"}
        if data is None or data.empty or not required.issubset(data.columns):
            return pd.DataFrame()
        result = data.copy()
        result["Datetime"] = pd.to_datetime(result["Datetime"], errors="coerce")
        try:
            if result["Datetime"].dt.tz is None:
                result["Datetime"] = result["Datetime"].dt.tz_localize(INDIA_TZ)
            else:
                result["Datetime"] = result["Datetime"].dt.tz_convert(INDIA_TZ)
        except Exception:
            return pd.DataFrame()
        for col in ("Open", "High", "Low", "Close"):
            result[col] = pd.to_numeric(result[col], errors="coerce")
        return result.dropna(subset=["Datetime", "Open", "High", "Low", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    @staticmethod
    def _current_minute():
        return datetime.now(INDIA_TZ).replace(second=0, microsecond=0)

    def _completed_prices(self, data):
        prices = self._clean_prices(data)
        if prices.empty:
            return prices
        now = self._current_minute()
        return prices[(prices["Datetime"] < now) & (prices["Datetime"].dt.date == now.date())].copy()

    def _trigger_candle(self, today_data, today_open, pdh, pdl, side):
        """Find the latest completed 1-minute reversal after price actually breaches PDH/PDL."""
        prices = self._completed_prices(today_data)
        if prices.empty:
            return None

        level = float(pdh if side == "BUY" else pdl)
        breached = False
        breach_time = None
        latest = None

        for _, row in prices.iterrows():
            stamp = row["Datetime"]
            candle_open = float(row["Open"])
            candle_high = float(row["High"])
            candle_low = float(row["Low"])
            candle_close = float(row["Close"])

            if side == "BUY":
                # Price must actually trade below PDH; a wick through PDH is sufficient.
                if candle_low < level:
                    breached = True
                    breach_time = stamp
                    continue
                # After the breach, the trigger candle must open below Today's Open
                # and close back above Today's Open.
                if breached and stamp > breach_time and self.start <= stamp.time() <= self.end and candle_open < float(today_open) and candle_close > float(today_open):
                    latest = row
            else:
                # Price must actually trade above PDL; a wick through PDL is sufficient.
                if candle_high > level:
                    breached = True
                    breach_time = stamp
                    continue
                # After the breach, the trigger candle must open above Today's Open
                # and close back below Today's Open.
                if breached and stamp > breach_time and self.start <= stamp.time() <= self.end and candle_open > float(today_open) and candle_close < float(today_open):
                    latest = row

        if latest is None:
            return None

        age_minutes = (self._current_minute() - latest["Datetime"]).total_seconds() / 60.0
        if age_minutes < 0 or age_minutes > float(MAX_TRIGGER_AGE_MINUTES):
            return None
        return latest

    @staticmethod
    def _trigger_key(symbol, trigger_time, side, nifty_change_pct):
        stamp = pd.Timestamp(trigger_time)
        stamp = stamp.tz_localize(INDIA_TZ) if stamp.tzinfo is None else stamp.tz_convert(INDIA_TZ)
        return (str(symbol).upper(), stamp.isoformat(), str(side).upper(), round(float(nifty_change_pct), 3))

    def _trade(self, side, symbol, trigger, today_open, pdh, pdl, nifty_change_pct):
        entry = float(trigger["Close"])
        stop = float(pdh) if side == "BUY" else float(pdl)
        risk = entry - stop if side == "BUY" else stop - entry
        if risk <= 0:
            return None
        target = entry + risk * self.rr if side == "BUY" else entry - risk * self.rr
        return {
            "symbol": symbol,
            "signal": side,
            "entry_time": trigger["Datetime"],
            "entry": round(entry, 2),
            "open_cross_level": round(float(today_open), 4),
            "stop_loss": round(stop, 4),
            "target": round(target, 2),
            "risk_per_share": round(risk, 4),
            "risk_reward": self.rr,
            "pdh": round(float(pdh), 4),
            "pdl": round(float(pdl), 4),
            "today_open": round(float(today_open), 4),
            "market_direction": "BULLISH" if nifty_change_pct >= 0.25 else "BEARISH",
            "nifty500_change_pct": round(float(nifty_change_pct), 4),
            "setup_type": "NIFTY_500_PDH_PDL_OPEN_REVERSAL_1M",
            "pdh_pdl_reached": True,
            "trigger_candle_open": round(float(trigger["Open"]), 4),
            "trigger_candle_high": round(float(trigger["High"]), 4),
            "trigger_candle_low": round(float(trigger["Low"]), 4),
            "trigger_candle_close": round(float(trigger["Close"]), 4),
            "trigger_close": round(float(trigger["Close"]), 4),
        }

    def build(self, symbol, prices, pdh, pdl, today_open=None, nifty_change_pct=0.0, nifty_candle=None):
        data = self._clean_prices(prices)
        if data.empty or pdh is None or pdl is None:
            return None

        today = datetime.now(INDIA_TZ).date()
        today_data = data[data["Datetime"].dt.date == today].copy()
        if today_data.empty:
            return None

        open_price = float(today_open) if today_open is not None else float(today_data.iloc[0]["Open"])
        change = float(nifty_change_pct)

        if ENABLE_LONG and open_price > float(pdh) and change >= 0.25:
            trigger = self._trigger_candle(today_data, open_price, float(pdh), float(pdl), "BUY")
            if trigger is not None:
                return self.finalize_trigger(symbol, trigger, open_price, pdh, pdl, "BUY", change)

        if ENABLE_SHORT and open_price < float(pdl) and change <= -0.25:
            trigger = self._trigger_candle(today_data, open_price, float(pdh), float(pdl), "SELL")
            if trigger is not None:
                return self.finalize_trigger(symbol, trigger, open_price, pdh, pdl, "SELL", change)

        return None

    def finalize_trigger(self, symbol, trigger, today_open, pdh, pdl, side, nifty_change_pct):
        key = self._trigger_key(symbol, trigger["Datetime"], side, nifty_change_pct)
        cached = self._finalized_triggers.get(key)
        if cached is not None:
            return cached.copy()
        signal = self._trade(side, symbol, trigger, today_open, pdh, pdl, nifty_change_pct)
        if signal is not None:
            self._finalized_triggers[key] = signal.copy()
        return signal
