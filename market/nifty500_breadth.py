"""Whole-universe NIFTY 500 advance/decline filter for strategy entries."""
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import time
import pandas as pd
from data.stock_universe import StockUniverse
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
CACHE_SECONDS = 10


class Nifty500Breadth:
    """Compute breadth across the complete NIFTY 500 universe.

    A trade is never allowed from a partial breadth sample. If all 500 members
    cannot be evaluated, the result is UNKNOWN and the hard breadth filter blocks
    the entry rather than pretending partial coverage is the full NIFTY 500.
    """
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.price_data = PriceData()
        self._lock = threading.RLock()
        self._cached_at = 0.0
        self._cached = None

    def snapshot(self, force=False):
        now = time.monotonic()
        with self._lock:
            if not force and self._cached is not None and now - self._cached_at < CACHE_SECONDS:
                return dict(self._cached)

        universe = self.universe_engine.get_dataframe(refresh=False)
        if universe is None or universe.empty or "Symbol" not in universe.columns:
            result = self._unknown("NIFTY_500_UNIVERSE_UNAVAILABLE")
            with self._lock:
                self._cached, self._cached_at = result, time.monotonic()
            return dict(result)

        symbols = universe["Symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False).drop_duplicates().tolist()[:500]
        total = len(symbols)
        if total < 500:
            result = self._unknown(f"NIFTY_500_UNIVERSE_ONLY_{total}", total)
            with self._lock:
                self._cached, self._cached_at = result, time.monotonic()
            return dict(result)

        intraday = self.price_data.get_multi_1m(symbols)
        daily = self.price_data.get_multi_daily(symbols, period="5d")
        today = datetime.now(INDIA_TZ).date()
        advances = declines = unchanged = evaluated = 0

        for symbol in symbols:
            current = None
            previous = None
            frame = intraday.get(symbol)
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                frame = frame.copy()
                frame["Datetime"] = pd.to_datetime(frame["Datetime"], errors="coerce")
                frame = frame.dropna(subset=["Datetime"])
                if not frame.empty:
                    current_rows = frame[frame["Datetime"].dt.date == today]
                    if not current_rows.empty:
                        current = float(current_rows.iloc[-1]["Close"])
            dframe = daily.get(symbol)
            if isinstance(dframe, pd.DataFrame) and not dframe.empty:
                dframe = dframe.copy()
                dframe["Datetime"] = pd.to_datetime(dframe["Datetime"], errors="coerce")
                dframe = dframe.dropna(subset=["Datetime"]).sort_values("Datetime")
                prior = dframe[dframe["Datetime"].dt.date < today]
                current_day = dframe[dframe["Datetime"].dt.date == today]
                if current is None and not current_day.empty:
                    current = float(current_day.iloc[-1]["Close"])
                if not prior.empty:
                    previous = float(prior.iloc[-1]["Close"])
            if current is None or previous is None or previous <= 0:
                continue
            evaluated += 1
            if current > previous:
                advances += 1
            elif current < previous:
                declines += 1
            else:
                unchanged += 1

        if evaluated != 500:
            result = self._unknown(f"INCOMPLETE_NIFTY_500_COVERAGE_{evaluated}_500", evaluated)
        else:
            ratio = float(advances / declines) if declines else float("inf")
            result = {
                "universe": "NIFTY 500",
                "total": 500,
                "evaluated": 500,
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "ad_ratio": ratio,
                "direction": "BULLISH" if advances > declines else "BEARISH" if declines > advances else "NEUTRAL",
                "complete": True,
                "reason": "OK",
                "updated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds"),
            }
        with self._lock:
            self._cached, self._cached_at = result, time.monotonic()
        return dict(result)

    @staticmethod
    def _unknown(reason, evaluated=0):
        return {
            "universe": "NIFTY 500",
            "total": 500,
            "evaluated": int(evaluated),
            "advances": 0,
            "declines": 0,
            "unchanged": 0,
            "ad_ratio": None,
            "direction": "UNKNOWN",
            "complete": False,
            "reason": reason,
            "updated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds"),
        }

    def allows(self, side):
        snap = self.snapshot()
        side = str(side).upper()
        if not snap.get("complete"):
            return False, snap
        if side == "BUY":
            return snap["advances"] > snap["declines"], snap
        if side == "SELL":
            return snap["declines"] > snap["advances"], snap
        return False, snap


BREADTH = Nifty500Breadth()
