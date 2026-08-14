"""PDH/PDL + Today's Open 1-minute reversal strategy."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import ENABLE_LONG, ENABLE_SHORT

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class PdhPdlOpenCrossEngine:
    """Generate signals after a PDH/PDL reaction followed by a 1-minute Open cross.

    SELL: today's Open is above PDH, price first reaches/touches PDH from above,
    then a completed 1-minute candle opens above today's Open and closes below it.

    BUY: today's Open is below PDL, price first reaches/touches PDL from below,
    then a completed 1-minute candle opens below today's Open and closes above it.
    """

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
        opening = float(df.iloc[0]["Open"])
        closing = float(df.iloc[-1]["Close"])
        if closing > opening:
            return "BULLISH"
        if closing < opening:
            return "BEARISH"
        return "NEUTRAL"

    def _trigger_candle(self, today_data, today_open, pdh, pdl, side):
        """Require a prior PDH/PDL reach, then an exact 1-minute Open cross."""
        data = self._clean(today_data)
        if len(data) < 2:
            return None

        current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        completed = data[data["Datetime"] < current_minute].copy()
        if completed.empty:
            return None

        level_reached = False
        level_reached_time = None

        for _, candle in completed.iterrows():
            candle_time = candle["Datetime"].time()
            if candle_time < self.start:
                continue
            if candle_time > self.end:
                break

            candle_open = float(candle["Open"])
            candle_high = float(candle["High"])
            candle_low = float(candle["Low"])
            candle_close = float(candle["Close"])

            if side == "SELL":
                # Today's Open is above PDH. Price must first come down to/touch PDH.
                if not level_reached and candle_low <= pdh:
                    level_reached = True
                    level_reached_time = candle["Datetime"]
                    continue
                # Trigger must occur after the PDH interaction, not on the same candle.
                if level_reached and candle["Datetime"] > level_reached_time:
                    if candle_open > today_open and candle_close < today_open:
                        return candle

            else:
                # Today's Open is below PDL. Price must first come up to/touch PDL.
                if not level_reached and candle_high >= pdl:
                    level_reached = True
                    level_reached_time = candle["Datetime"]
                    continue
                # Trigger must occur after the PDL interaction, not on the same candle.
                if level_reached and candle["Datetime"] > level_reached_time:
                    if candle_open < today_open and candle_close > today_open:
                        return candle

        return None

    def build(self, symbol, candles, pdh, pdl, today_open=None, sector_direction="UNKNOWN", nifty_direction="UNKNOWN"):
        data = self._clean(candles)
        if data.empty or pdh is None or pdl is None:
            return None

        pdh = float(pdh)
        pdl = float(pdl)
        latest_date = data["Datetime"].dt.date.max()
        today_data = data[data["Datetime"].dt.date == latest_date].copy()
        if today_data.empty:
            return None

        today_open = float(today_open) if today_open is not None else float(today_data.iloc[0]["Open"])
        today_low = float(today_data["Low"].min())
        today_high = float(today_data["High"].max())
        stock_today_direction = self._direction(today_data)

        if ENABLE_SHORT and today_open > pdh:
            if sector_direction == "BEARISH" and nifty_direction == "BEARISH":
                trigger = self._trigger_candle(today_data, today_open, pdh, pdl, "SELL")
                if trigger is not None and stock_today_direction == "BEARISH":
                    # Actual execution price is supplied by the paper-trading layer after the trigger.
                    trigger_close = float(trigger["Close"])
                    stop = today_high
                    return self._trade(
                        "SELL", symbol, trigger, trigger_close, stop, pdh, pdl, today_open,
                        today_low, today_high, sector_direction, nifty_direction, stock_today_direction,
                    )

        if ENABLE_LONG and today_open < pdl:
            if sector_direction == "BULLISH" and nifty_direction == "BULLISH":
                trigger = self._trigger_candle(today_data, today_open, pdh, pdl, "BUY")
                if trigger is not None and stock_today_direction == "BULLISH":
                    trigger_close = float(trigger["Close"])
                    stop = today_low
                    return self._trade(
                        "BUY", symbol, trigger, trigger_close, stop, pdh, pdl, today_open,
                        today_low, today_high, sector_direction, nifty_direction, stock_today_direction,
                    )
        return None

    def _trade(self, side, symbol, candle, trigger_close, stop, pdh, pdl, today_open,
               today_low, today_high, sector_direction, nifty_direction, stock_today_direction):
        return {
            "symbol": symbol,
            "signal": side,
            "entry_time": candle["Datetime"],
            "entry": round(trigger_close, 2),
            "breakout_level": round(today_open, 2),
            "stop_loss": round(stop, 2),
            "target": round(trigger_close + (trigger_close - stop) * self.rr, 2) if side == "BUY" else round(trigger_close - (stop - trigger_close) * self.rr, 2),
            "risk_reward": self.rr,
            "pdh": round(pdh, 4),
            "pdl": round(pdl, 4),
            "today_open": round(today_open, 4),
            "today_low": round(today_low, 4),
            "today_high": round(today_high, 4),
            "market_direction": nifty_direction,
            "nifty100_direction": nifty_direction,
            "sector_direction": sector_direction,
            "industry_direction": sector_direction,
            "stock_direction": stock_today_direction,
            "stock_today_direction": stock_today_direction,
            "setup_type": "PDH_PDL_OPEN_CROSS",
            "trigger_candle_open": round(float(candle["Open"]), 4),
            "trigger_candle_close": round(float(candle["Close"]), 4),
            "trigger_close": round(trigger_close, 4),
            "pdh_pdl_reached": True,
        }
