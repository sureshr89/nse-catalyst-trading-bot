"""Pure price-action Gap-Failure + Open-Reclaim strategy."""
from datetime import time
import pandas as pd


class GapReclaimEngine:
    def __init__(self, trading_start="09:45", last_entry_time="14:00", rr=1.5):
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
        if any(c not in data.columns for c in ["Datetime", "Open", "High", "Low", "Close"]):
            return pd.DataFrame()
        data["Datetime"] = pd.to_datetime(data["Datetime"], errors="coerce")
        for c in ["Open", "High", "Low", "Close"]:
            data[c] = pd.to_numeric(data[c], errors="coerce")
        return (data.dropna(subset=["Datetime", "Open", "High", "Low", "Close"])
                .sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True))

    def _entry_after_failure(self, df, today_open, pdc, side):
        data = self._clean(df)
        if len(data) < 3:
            return None
        completed = data.iloc[:-1].copy()
        if side == "BUY":
            breach_positions = completed.index[completed["Low"] < pdc].tolist()
        else:
            breach_positions = completed.index[completed["High"] > pdc].tolist()
        if not breach_positions:
            return None
        breach_pos = breach_positions[0]
        for i in range(max(1, breach_pos + 1), len(completed)):
            prev_close = float(completed.iloc[i - 1]["Close"])
            candle = completed.iloc[i]
            close = float(candle["Close"])
            t = candle["Datetime"].time()
            if t < self.start or t > self.end:
                continue
            if side == "BUY" and prev_close <= today_open and close > today_open:
                return candle
            if side == "SELL" and prev_close >= today_open and close < today_open:
                return candle
        return None

    def build(self, symbol, candles, pdc, previous_day_open, sector_direction, nifty_direction):
        data = self._clean(candles)
        if data.empty or pdc is None or previous_day_open is None:
            return None
        pdc = float(pdc)
        previous_day_open = float(previous_day_open)
        today_open = float(data.iloc[0]["Open"])
        today_low = float(data["Low"].min())
        today_high = float(data["High"].max())
        previous_day_green = pdc > previous_day_open
        previous_day_red = pdc < previous_day_open

        if previous_day_green and today_open > pdc and today_low < pdc:
            if sector_direction == "BULLISH" and nifty_direction == "BULLISH":
                candle = self._entry_after_failure(data, today_open, pdc, "BUY")
                if candle is not None:
                    entry = float(candle["Close"])
                    stop = today_low
                    risk = entry - stop
                    if risk > 0:
                        return self._trade("BUY", symbol, candle, entry, stop, entry + risk * self.rr,
                                           pdc, today_open, today_low, today_high, sector_direction,
                                           nifty_direction, previous_day_green)

        if previous_day_red and today_open < pdc and today_high > pdc:
            if sector_direction == "BEARISH" and nifty_direction == "BEARISH":
                candle = self._entry_after_failure(data, today_open, pdc, "SELL")
                if candle is not None:
                    entry = float(candle["Close"])
                    stop = today_high
                    risk = stop - entry
                    if risk > 0:
                        return self._trade("SELL", symbol, candle, entry, stop, entry - risk * self.rr,
                                           pdc, today_open, today_low, today_high, sector_direction,
                                           nifty_direction, previous_day_red)
        return None

    def _trade(self, side, symbol, candle, entry, stop, target, pdc, today_open,
               today_low, today_high, sector_direction, nifty_direction, previous_aligned):
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
            "nifty100_direction": nifty_direction,
            "previous_day_aligned": bool(previous_aligned),
            "setup_type": "GAP_FAILURE_OPEN_RECLAIM",
            "entry_candle_close": round(float(candle["Close"]), 2),
        }
