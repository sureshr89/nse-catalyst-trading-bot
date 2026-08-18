"""NIFTY 500 PDH/PDL + Today's Open return strategy.

All active triggers are LIVE LTP rules. Completed candles are never used as
entry confirmation, breach confirmation, return confirmation, SL, or target.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import ENABLE_LONG, ENABLE_SHORT, NIFTY500_MIN_CHANGE_PCT
from strategy.contracts import STRATEGY_VERSION, STRATEGY_1_NAME
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
_LIVE = PriceData()


class OpenReversalEngine:
    """PDH/PDL + Today's Open reversal using live LTP trigger conditions."""
    strategy_id = "STRATEGY_1"
    strategy_name = STRATEGY_1_NAME
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
    def clean_prices(data):
        if data is None or data.empty or "Datetime" not in data.columns or "Close" not in data.columns:
            return pd.DataFrame()
        result = data.copy()
        result["Datetime"] = pd.to_datetime(result["Datetime"], errors="coerce")
        try:
            result["Datetime"] = result["Datetime"].dt.tz_localize(INDIA_TZ) if result["Datetime"].dt.tz is None else result["Datetime"].dt.tz_convert(INDIA_TZ)
        except Exception:
            return pd.DataFrame()
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")
        return result.dropna(subset=["Datetime", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

    @staticmethod
    def latest_completed(data):
        prices = OpenReversalEngine.clean_prices(data)
        if prices.empty:
            return None
        current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        completed = prices[prices["Datetime"] < current_minute]
        return None if completed.empty else completed.iloc[-1]

    @staticmethod
    def completed_only(data):
        prices = OpenReversalEngine.clean_prices(data)
        if prices.empty:
            return prices
        current_minute = datetime.now(INDIA_TZ).replace(second=0, microsecond=0)
        return prices[prices["Datetime"] < current_minute].copy()

    def initial_side(self, today_open, pdh, pdl):
        if ENABLE_LONG and float(today_open) > float(pdh):
            return "BUY"
        if ENABLE_SHORT and float(today_open) < float(pdl):
            return "SELL"
        return None

    @staticmethod
    def _live(symbol):
        try:
            if not symbol:
                return None
            return _LIVE.get_latest_live_price(str(symbol), max_age_seconds=2)
        except Exception:
            return None

    def update_state(self, state, today_open, pdh, pdl, completed_close=None, stamp=None):
        """Evaluate ONLY the current live LTP.

        The completed_close/stamp arguments remain for API compatibility but are
        deliberately ignored. This prevents a completed candle from qualifying
        a breach or return after the user explicitly requested no candle-close
        confirmation.
        """
        state = dict(state)
        side = str(state.get("side", "")).upper()
        open_price = float(today_open)
        pdh = float(pdh)
        pdl = float(pdl)
        symbol = str(state.get("symbol", "")).strip().upper()
        live = self._live(symbol)
        if live is None:
            return state
        try:
            ltp = float(live.get("Close"))
        except (TypeError, ValueError):
            return state
        if ltp <= 0:
            return state

        now = datetime.now(INDIA_TZ).isoformat(timespec="milliseconds")
        if side == "BUY":
            if not state.get("pdh_breached") and ltp <= pdh:
                state["pdh_breached"] = True
                state["pdh_breach_time"] = now
                state["breach_price"] = ltp
            if state.get("pdh_breached") and ltp >= open_price:
                state["open_returned"] = True
                state["qualified_time"] = now
                state["qualified_ltp"] = ltp
                state["trigger_price"] = ltp
        elif side == "SELL":
            if not state.get("pdl_breached") and ltp >= pdl:
                state["pdl_breached"] = True
                state["pdl_breach_time"] = now
                state["breach_price"] = ltp
            if state.get("pdl_breached") and ltp <= open_price:
                state["open_returned"] = True
                state["qualified_time"] = now
                state["qualified_ltp"] = ltp
                state["trigger_price"] = ltp
        return state

    def market_aligned(self, side, nifty_change_pct):
        change = float(nifty_change_pct)
        return change >= NIFTY500_MIN_CHANGE_PCT if side == "BUY" else change <= -NIFTY500_MIN_CHANGE_PCT

    def build_signal(self, symbol, side, entry, today_open, pdh, pdl, nifty_change_pct, metrics=None):
        entry = float(entry)
        stop = float(pdh) if side == "BUY" else float(pdl)
        risk = entry - stop if side == "BUY" else stop - entry
        if risk <= 0:
            return None
        target = entry + risk * self.rr if side == "BUY" else entry - risk * self.rr
        now = datetime.now(INDIA_TZ)
        signal = {
            "symbol": str(symbol).upper(),
            "strategy": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "signal": side,
            "entry_time": now.isoformat(timespec="milliseconds"),
            "trigger_entry_time": now.isoformat(timespec="milliseconds"),
            "market_entry_time": now.isoformat(timespec="milliseconds"),
            "entry": round(entry, 4),
            "open_cross_level": round(float(today_open), 4),
            "stop_loss": round(stop, 4),
            "target": round(target, 4),
            "risk_per_share": round(risk, 4),
            "risk_reward": self.rr,
            "pdh": round(float(pdh), 4),
            "pdl": round(float(pdl), 4),
            "today_open": round(float(today_open), 4),
            "nifty500_change_pct": round(float(nifty_change_pct), 4),
            "market_direction": "BULLISH" if side == "BUY" else "BEARISH",
            "setup_type": "NIFTY_500_PDH_PDL_OPEN_RETURN_LIVE_LTP",
            "pdh_pdl_reached": True,
            "entry_source": "LIVE_LTP",
            "trigger_price": round(entry, 4),
        }
        if metrics:
            signal.update({k: v for k, v in metrics.items() if "atr" not in str(k).lower() and "average_true_range" not in str(k).lower()})
        return signal

    def build(self, symbol, prices, pdh, pdl, today_open=None, nifty_change_pct=0.0, nifty_candle=None):
        data = self.completed_only(prices)
        if data.empty or pdh is None or pdl is None:
            return None
        today = datetime.now(INDIA_TZ).date()
        today_data = data[data["Datetime"].dt.date == today]
        if today_data.empty:
            return None
        open_price = float(today_open) if today_open is not None else float(today_data.iloc[0]["Open"])
        side = self.initial_side(open_price, pdh, pdl)
        if side is None or not self.market_aligned(side, nifty_change_pct):
            return None
        state = {"symbol": symbol, "side": side, "pdh_breached": False, "pdl_breached": False, "open_returned": False}
        for _ in today_data.itertuples():
            state = self.update_state(state, open_price, pdh, pdl)
            if state.get("open_returned"):
                break
        if not state.get("open_returned"):
            return None
        live = self._live(symbol)
        if live is None:
            return None
        entry = float(live["Close"])
        return self.build_signal(symbol, side, entry, open_price, pdh, pdl, nifty_change_pct)
