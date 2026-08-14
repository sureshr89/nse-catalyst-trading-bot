"""NIFTY 500 PDH/PDL + today's Open 1-minute reversal strategy."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import ENABLE_LONG, ENABLE_SHORT, MAX_TRIGGER_AGE_MINUTES

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class OpenReversalEngine:
    """Build a fresh signal after the correct PDH/PDL break and completed Open cross."""

    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.25):
        self.start = self._time(trading_start)
        self.end = self._time(last_entry_time)
        self.rr = float(rr)

    @staticmethod
    def _time(value):
        h, m = map(int, str(value).split(":"))
        return time(h, m)

    @staticmethod
    def _clean(df):
        if df is None or df.empty:
            return pd.DataFrame()
        data = df.copy()
        required = ["Datetime", "Open", "High", "Low", "Close"]
        if any(c not in data.columns for c in required):
            return pd.DataFrame()
        data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
        try:
            if getattr(data["Datetime"].dt, "tz", None) is None:
                data["Datetime"] = data["Datetime"].dt.tz_localize(INDIA_TZ)
            else:
                data["Datetime"] = data["Datetime"].dt.tz_convert(INDIA_TZ)
        except Exception:
            return pd.DataFrame()
        for column in ["Open", "High", "Low", "Close"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        return data.dropna(subset=required).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    @staticmethod
    def _direction(df):
        if df is None or df.empty:
            return "UNKNOWN"
        opening, closing = float(df.iloc[0]["Open"]), float(df.iloc[-1]["Close"])
        return "BULLISH" if closing > opening else "BEARISH" if closing < opening else "NEUTRAL"

    def _trigger_candle(self, today_data, today_open, pdh, pdl, side):
        data = self._clean(today_data)
        if len(data) < 2:
            return None
        current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        completed = data[data["Datetime"] < current_minute].copy()
        if completed.empty:
            return None

        level_reached = False
        level_reached_time = None
        latest_trigger = None
        for _, candle in completed.iterrows():
            candle_time = candle["Datetime"].time()
            if candle_time > self.end:
                break

            if side == "BUY":
                if not level_reached and float(candle["Low"]) < pdh:
                    level_reached = True
                    level_reached_time = candle["Datetime"]
                    continue
                if level_reached and candle_time >= self.start and candle["Datetime"] > level_reached_time:
                    if float(candle["Open"]) < today_open and float(candle["Close"]) > today_open:
                        latest_trigger = candle
            else:
                if not level_reached and float(candle["High"]) > pdl:
                    level_reached = True
                    level_reached_time = candle["Datetime"]
                    continue
                if level_reached and candle_time >= self.start and candle["Datetime"] > level_reached_time:
                    if float(candle["Open"]) > today_open and float(candle["Close"]) < today_open:
                        latest_trigger = candle
        return latest_trigger

    def _fresh(self, trigger):
        age = (datetime.now(INDIA_TZ) - trigger["Datetime"]).total_seconds() / 60.0
        return 0 <= age <= float(MAX_TRIGGER_AGE_MINUTES)

    def build(self, symbol, candles, pdh, pdl, today_open=None, sector_direction="UNKNOWN", nifty_direction="UNKNOWN"):
        data = self._clean(candles)
        if data.empty or pdh is None or pdl is None:
            return None
        pdh, pdl = float(pdh), float(pdl)
        latest_date = data["Datetime"].dt.date.max()
        today_data = data[data["Datetime"].dt.date == latest_date].copy()
        if today_data.empty:
            return None
        today_open = float(today_open) if today_open is not None else float(today_data.iloc[0]["Open"])

        if ENABLE_LONG and today_open > pdh:
            trigger = self._trigger_candle(today_data, today_open, pdh, pdl, "BUY")
            if trigger is not None and self._fresh(trigger):
                setup_data = today_data[today_data["Datetime"] <= trigger["Datetime"]]
                stock_direction = self._direction(setup_data)
                return self._trade(
                    "BUY", symbol, trigger, today_open, pdh, pdl,
                    float(setup_data["Low"].min()), float(setup_data["High"].max()),
                    sector_direction, nifty_direction, stock_direction,
                )

        if ENABLE_SHORT and today_open < pdl:
            trigger = self._trigger_candle(today_data, today_open, pdh, pdl, "SELL")
            if trigger is not None and self._fresh(trigger):
                setup_data = today_data[today_data["Datetime"] <= trigger["Datetime"]]
                stock_direction = self._direction(setup_data)
                return self._trade(
                    "SELL", symbol, trigger, today_open, pdh, pdl,
                    float(setup_data["Low"].min()), float(setup_data["High"].max()),
                    sector_direction, nifty_direction, stock_direction,
                )
        return None

    def _trade(self, side, symbol, candle, today_open, pdh, pdl, today_low, today_high, sector_direction, nifty_direction, stock_direction):
        trigger_close = float(candle["Close"])
        stop = today_high if side == "SELL" else today_low
        reward_distance = abs(trigger_close - stop) * self.rr
        target = trigger_close + reward_distance if side == "BUY" else trigger_close - reward_distance
        return {
            "symbol": symbol, "signal": side, "entry_time": candle["Datetime"], "entry": round(trigger_close, 2),
            "open_cross_level": round(today_open, 4), "stop_loss": round(stop, 4), "target": round(target, 2),
            "risk_reward": self.rr, "pdh": round(pdh, 4), "pdl": round(pdl, 4), "today_open": round(today_open, 4),
            "today_low": round(today_low, 4), "today_high": round(today_high, 4), "market_direction": nifty_direction,
            "sector_direction": sector_direction, "stock_direction": stock_direction, "stock_today_direction": stock_direction,
            "setup_type": "NIFTY_500_PDH_PDL_OPEN_REVERSAL", "trigger_candle_open": round(float(candle["Open"]), 4),
            "trigger_candle_close": round(trigger_close, 4), "trigger_close": round(trigger_close, 4), "pdh_pdl_reached": True,
        }
