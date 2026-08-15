"""Direct 1-minute price strategy for the NIFTY 500 PDH/PDL + Today's Open reversal setup."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import ENABLE_LONG, ENABLE_SHORT

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class OpenReversalEngine:
    """Generate signals from 1-minute prices only; no candlestick confirmation is required."""

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
        if data is None or data.empty or "Datetime" not in data.columns or "Close" not in data.columns:
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
        result["Close"] = pd.to_numeric(result["Close"], errors="coerce")
        return result.dropna(subset=["Datetime", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    @staticmethod
    def _current_minute():
        return datetime.now(INDIA_TZ).replace(second=0, microsecond=0)

    def _completed_prices(self, data):
        prices = self._clean_prices(data)
        if prices.empty:
            return prices
        current_minute = self._current_minute()
        return prices[(prices["Datetime"] < current_minute) & (prices["Datetime"].dt.date == current_minute.date())].copy()

    def _trigger_price(self, today_data, today_open, pdh, pdl, side):
        """Find the latest completed price that proves the required sequence.

        BUY: Open > PDH -> price was below PDH -> price returned to Today's Open.
        SELL: Open < PDL -> price was above PDL -> price returned to Today's Open.
        """
        prices = self._completed_prices(today_data)
        if prices.empty:
            return None
        prices = prices[prices["Datetime"].dt.time <= self.end]
        prices = prices[prices["Datetime"].dt.time >= self.start]
        if prices.empty:
            return None

        level = float(pdh if side == "BUY" else pdl)
        breached = False
        breach_time = None
        for _, row in prices.iterrows():
            price = float(row["Close"])
            stamp = row["Datetime"]
            if side == "BUY":
                if price < level:
                    breached = True
                    breach_time = stamp
                    continue
                if breached and stamp > breach_time and price >= float(today_open):
                    return row
            else:
                if price > level:
                    breached = True
                    breach_time = stamp
                    continue
                if breached and stamp > breach_time and price <= float(today_open):
                    return row
        return None

    @staticmethod
    def _trigger_key(symbol, trigger_time, side, nifty_change_pct):
        stamp = pd.Timestamp(trigger_time)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(INDIA_TZ)
        else:
            stamp = stamp.tz_convert(INDIA_TZ)
        return (str(symbol).upper(), stamp.isoformat(), str(side).upper(), round(float(nifty_change_pct), 3))

    def _trade(self, side, symbol, trigger_time, today_open, pdh, pdl, nifty_change_pct):
        entry = float(today_open)
        stop = float(pdh) if side == "BUY" else float(pdl)
        risk = abs(entry - stop)
        if risk <= 0:
            return None
        target_distance = risk * self.rr
        target = entry + target_distance if side == "BUY" else entry - target_distance
        return {
            "symbol": symbol,
            "signal": side,
            "entry_time": trigger_time,
            "entry": round(entry, 2),
            "open_cross_level": round(entry, 4),
            "stop_loss": round(stop, 4),
            "target": round(target, 2),
            "risk_per_share": round(risk, 4),
            "risk_reward": self.rr,
            "pdh": round(float(pdh), 4),
            "pdl": round(float(pdl), 4),
            "today_open": round(entry, 4),
            "market_direction": "BULLISH" if nifty_change_pct >= 0.25 else "BEARISH" if nifty_change_pct <= -0.25 else "NEUTRAL",
            "nifty500_change_pct": round(float(nifty_change_pct), 4),
            "setup_type": "NIFTY_500_PDH_PDL_OPEN_PRICE_REVERSAL",
            "pdh_pdl_reached": True,
        }

    def build(self, symbol, prices, pdh, pdl, today_open=None, nifty_change_pct=0.0, nifty_candle=None):
        data = self._clean_prices(prices)
        if data.empty or pdh is None or pdl is None:
            return None
        today = datetime.now(INDIA_TZ).date()
        today_data = data[data["Datetime"].dt.date == today].copy()
        if today_data.empty:
            return None
        today_open = float(today_open) if today_open is not None else float(today_data.iloc[0]["Close"])
        market_change = float(nifty_change_pct)

        if ENABLE_LONG and today_open > float(pdh) and market_change >= 0.25:
            trigger = self._trigger_price(today_data, today_open, float(pdh), float(pdl), "BUY")
            if trigger is not None:
                return self.finalize_trigger(symbol, trigger["Datetime"], today_open, pdh, pdl, "BUY", market_change)

        if ENABLE_SHORT and today_open < float(pdl) and market_change <= -0.25:
            trigger = self._trigger_price(today_data, today_open, float(pdh), float(pdl), "SELL")
            if trigger is not None:
                return self.finalize_trigger(symbol, trigger["Datetime"], today_open, pdh, pdl, "SELL", market_change)
        return None

    def finalize_trigger(self, symbol, trigger_time, today_open, pdh, pdl, side, nifty_change_pct):
        if trigger_time is None:
            return None
        key = self._trigger_key(symbol, trigger_time, side, nifty_change_pct)
        cached = self._finalized_triggers.get(key)
        if cached is not None:
            return cached.copy()
        signal = self._trade(side, symbol, trigger_time, today_open, pdh, pdl, nifty_change_pct)
        if signal is not None:
            self._finalized_triggers[key] = signal.copy()
        return signal
