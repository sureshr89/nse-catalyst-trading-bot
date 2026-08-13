"""Pure price-action Gap-Failure + Open-Reclaim strategy."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import ENABLE_LONG, ENABLE_SHORT

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class GapReclaimEngine:
    """Build BUY/SELL signals from PDC, today's OHLC and alignment."""

    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.25):
        self.start = self._time(trading_start)
        self.end = self._time(last_entry_time)
        self.rr = float(rr)

    @staticmethod
    def _time(value):
        h, m = map(int, str(value).split(":"))
        return time(h, m)

    @classmethod
    def _clean(cls, df):
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
        for c in ["Open", "High", "Low", "Close"]:
            data[c] = pd.to_numeric(data[c], errors="coerce")
        return (
            data.dropna(subset=required)
            .sort_values("Datetime")
            .drop_duplicates("Datetime")
            .reset_index(drop=True)
        )

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

    def _entry_candle(self, df, today_open, pdc, side):
        """Return the first later completed candle that reclaims today's open after a PDC failure."""
        data = self._clean(df)
        if len(data) < 2:
            return None

        current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        completed = data[data["Datetime"] < current_minute].copy()
        if len(completed) < 2:
            return None

        pdc_breached = False
        for i in range(len(completed)):
            cur = completed.iloc[i]

            if i == 0:
                if side == "BUY" and float(cur["Low"]) < pdc:
                    pdc_breached = True
                elif side == "SELL" and float(cur["High"]) > pdc:
                    pdc_breached = True
                continue

            cur_time = cur["Datetime"].time()
            if cur_time < self.start:
                if side == "BUY" and float(cur["Low"]) < pdc:
                    pdc_breached = True
                elif side == "SELL" and float(cur["High"]) > pdc:
                    pdc_breached = True
                continue
            if cur_time > self.end:
                break

            if not pdc_breached:
                if side == "BUY" and float(cur["Low"]) < pdc:
                    pdc_breached = True
                elif side == "SELL" and float(cur["High"]) > pdc:
                    pdc_breached = True
                continue

            candle_low = float(cur["Low"])
            candle_high = float(cur["High"])
            candle_close = float(cur["Close"])

            if side == "BUY" and candle_low < today_open and candle_close > today_open:
                return cur

            if side == "SELL" and candle_high > today_open and candle_close < today_open:
                return cur

            if side == "BUY" and candle_low < pdc:
                pdc_breached = True
            elif side == "SELL" and candle_high > pdc:
                pdc_breached = True

        return None

    def build(self, symbol, candles, pdc, previous_day_open, sector_direction, nifty_direction):
        data = self._clean(candles)
        if data.empty or pdc is None or previous_day_open is None:
            return None

        pdc = float(pdc)
        previous_day_open = float(previous_day_open)
        latest_date = data["Datetime"].dt.date.max()
        today_data = data[data["Datetime"].dt.date == latest_date].copy()
        if today_data.empty:
            return None

        today_open = float(today_data.iloc[0]["Open"])
        today_low = float(today_data["Low"].min())
        today_high = float(today_data["High"].max())
        previous_day_green = pdc > previous_day_open
        previous_day_red = pdc < previous_day_open
        previous_day_direction = "BULLISH" if previous_day_green else "BEARISH" if previous_day_red else "NEUTRAL"
        stock_today_direction = self._direction(today_data)

        if ENABLE_LONG and previous_day_green and today_open > pdc:
            if today_low < pdc and sector_direction == "BULLISH" and nifty_direction == "BULLISH":
                entry_candle = self._entry_candle(today_data, today_open, pdc, "BUY")
                if entry_candle is not None and stock_today_direction == "BULLISH":
                    entry = float(entry_candle["Close"])
                    stop = today_low
                    risk = entry - stop
                    if risk > 0:
                        return self._trade("BUY", symbol, entry_candle, entry, stop, entry + risk * self.rr, pdc, today_open, today_low, today_high, sector_direction, nifty_direction, previous_day_direction, stock_today_direction)

        if ENABLE_SHORT and previous_day_red and today_open < pdc:
            if today_high > pdc and sector_direction == "BEARISH" and nifty_direction == "BEARISH":
                entry_candle = self._entry_candle(today_data, today_open, pdc, "SELL")
                if entry_candle is not None and stock_today_direction == "BEARISH":
                    entry = float(entry_candle["Close"])
                    stop = today_high
                    risk = stop - entry
                    if risk > 0:
                        return self._trade("SELL", symbol, entry_candle, entry, stop, entry - risk * self.rr, pdc, today_open, today_low, today_high, sector_direction, nifty_direction, previous_day_direction, stock_today_direction)
        return None

    def _trade(self, side, symbol, candle, entry, stop, target, pdc, today_open, today_low, today_high, sector_direction, nifty_direction, previous_day_direction, stock_today_direction):
        return {
            "symbol": symbol,
            "signal": side,
            "entry_time": candle["Datetime"],
            "entry": round(entry, 2),
            "breakout_level": round(today_open, 2),
            "stop_loss": round(stop, 2),
            "target": round(target, 2),
            "risk_reward": self.rr,
            "pdc": round(pdc, 2),
            "today_open": round(today_open, 2),
            "today_low": round(today_low, 2),
            "today_high": round(today_high, 2),
            "sector_direction": sector_direction,
            "industry_direction": sector_direction,
            "market_direction": nifty_direction,
            "nifty100_direction": nifty_direction,
            "stock_direction": stock_today_direction,
            "stock_today_direction": stock_today_direction,
            "previous_day_aligned": previous_day_direction == ("BULLISH" if side == "BUY" else "BEARISH"),
            "previous_day_direction": previous_day_direction,
            "setup_type": "GAP_FAILURE_OPEN_RECLAIM",
            "entry_candle_open": round(float(candle["Open"]), 2),
            "entry_candle_close": round(float(candle["Close"]), 2),
        }
