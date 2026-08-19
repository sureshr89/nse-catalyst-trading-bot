"""NIFTY 500 breadth and sector alignment using DhanHQ market data."""
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import threading
import time
import pandas as pd

from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.dhan_data import configured as dhan_configured, map_nifty500, market_quote, index_quote

INDIA_TZ = ZoneInfo("Asia/Kolkata")
CACHE_SECONDS = 15
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)

class Nifty500Breadth:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self._lock = threading.RLock()
        self._cached_at = 0.0
        self._cached = None
        self._mapping = pd.DataFrame()
        self._mapping_at = 0.0
        self._universe = pd.DataFrame()

    def _get_universe(self):
        if self._universe is not None and len(self._universe) == 500:
            return self._universe
        universe = self.universe_engine.get_dataframe(refresh=True)
        if universe is None or universe.empty or "Symbol" not in universe.columns:
            return pd.DataFrame()
        universe = universe.copy()
        universe["Symbol"] = universe["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
        universe = universe.drop_duplicates("Symbol").head(500).reset_index(drop=True)
        if len(universe) == 500:
            self._universe = universe
        return universe

    def _get_mapping(self, symbols):
        now = time.monotonic()
        if self._mapping is not None and not self._mapping.empty and now - self._mapping_at < 3600:
            if set(self._mapping["Symbol"].astype(str).str.upper()) == set(symbols):
                return self._mapping
        mapping = map_nifty500(symbols)
        self._mapping = mapping
        self._mapping_at = now
        return mapping

    @staticmethod
    def _closed_session_mode(now):
        t = now.timetz().replace(tzinfo=None)
        return t >= MARKET_CLOSE or t < MARKET_OPEN

    def snapshot(self, force=False):
        now = datetime.now(INDIA_TZ)
        closed_mode = self._closed_session_mode(now)
        cache_key = "closed" if closed_mode else "live"
        mono = time.monotonic()
        with self._lock:
            if not force and self._cached is not None and now.date() == self._cached.get("_cache_date") and cache_key == self._cached.get("_cache_mode") and mono - self._cached_at < CACHE_SECONDS:
                return dict(self._cached)

        universe = self._get_universe()
        if universe is None or universe.empty or "Symbol" not in universe.columns:
            return self._store(self._unknown("NIFTY_500_UNIVERSE_UNAVAILABLE", cache_key, now))
        symbols = universe["Symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False).drop_duplicates().tolist()
        if len(symbols) != 500:
            return self._store(self._unknown(f"NIFTY_500_UNIVERSE_ONLY_{len(symbols)}", cache_key, now, len(symbols)))
        if not dhan_configured():
            return self._store(self._unknown("DHAN_NOT_CONFIGURED", cache_key, now))
        mapping = self._get_mapping(symbols)
        if len(mapping) != 500:
            return self._store(self._unknown(f"DHAN_SECURITY_MAPPING_{len(mapping)}/500", cache_key, now, len(mapping)))

        quotes = market_quote(mapping, cache_seconds=10)
        if quotes.empty or len(quotes) != 500:
            return self._store(self._unknown(f"DHAN_MARKET_DATA_{len(quotes)}/500", cache_key, now, len(quotes)))
        quotes["LTP"] = pd.to_numeric(quotes["LTP"], errors="coerce")
        quotes["PreviousClose"] = pd.to_numeric(quotes["PreviousClose"], errors="coerce")
        quotes["TodayClose"] = pd.to_numeric(quotes.get("TodayClose"), errors="coerce")

        if closed_mode:
            quotes["SessionClose"] = quotes["TodayClose"]
            bad = quotes["SessionClose"].isna() | (quotes["SessionClose"] <= 0)
            quotes.loc[bad, "SessionClose"] = quotes.loc[bad, "LTP"]
            session_basis = "Dhan completed-session close"
        else:
            quotes["SessionClose"] = quotes["LTP"]
            session_basis = "Dhan live LTP"

        quotes = quotes.dropna(subset=["SessionClose", "PreviousClose"])
        quotes = quotes[(quotes["SessionClose"] > 0) & (quotes["PreviousClose"] > 0)]
        if len(quotes) != 500:
            return self._store(self._unknown(f"DHAN_VALID_PRICE_DATA_{len(quotes)}/500", cache_key, now, len(quotes)))

        quotes["change_pct"] = (quotes["SessionClose"] - quotes["PreviousClose"]) / quotes["PreviousClose"] * 100
        advances = int((quotes["change_pct"] > 0).sum())
        declines = int((quotes["change_pct"] < 0).sum())
        unchanged = int((quotes["change_pct"] == 0).sum())
        ad_ratio = float(advances / declines) if declines else float("inf")

        try:
            sector_map = load_sector_map(universe, refresh=False)
            sector = calculate_sector_alignment(quotes[["Symbol", "change_pct"]], sector_map, "change_pct")
        except Exception as exc:
            sector = {"available": False, "alignment_pct": None, "mapped": 0, "priced": 0, "sectors": 0, "positive_sectors": 0, "negative_sectors": 0, "coverage": "0/500", "error": str(exc)}

        nifty = index_quote("NIFTY 500")
        if not nifty:
            return self._store(self._unknown("DHAN_NIFTY500_INDEX_UNAVAILABLE", cache_key, now, 500, sector=sector))
        prev_close = float(nifty.get("PreviousClose") or 0)
        live_ltp = float(nifty.get("LTP") or 0)
        day_close = float(nifty.get("Close") or 0)
        if closed_mode:
            session_close = day_close if day_close > 0 else live_ltp
            nifty_change = ((session_close - prev_close) / prev_close * 100) if prev_close > 0 else None
            display_close = session_close
            session_label = "Latest completed NSE session"
            updated_label = f"Latest completed session • market close 15:30 IST • refreshed {now.strftime('%H:%M:%S')} IST"
        else:
            nifty_change = ((live_ltp - prev_close) / prev_close * 100) if prev_close > 0 else None
            display_close = prev_close
            session_label = "Previous completed NSE session"
            updated_label = f"Previous completed session • close 15:30 IST • refreshed {now.strftime('%H:%M:%S')} IST"
        if not display_close or not prev_close or nifty_change is None:
            return self._store(self._unknown("DHAN_NIFTY500_CLOSED_PRICE_UNAVAILABLE", cache_key, now, 500, sector=sector))

        result = {
            "universe": "NIFTY 500", "total": 500, "evaluated": 500,
            "advances": advances, "declines": declines, "unchanged": unchanged, "ad_ratio": ad_ratio,
            "direction": "BULLISH" if advances > declines else "BEARISH" if declines > advances else "NEUTRAL",
            "complete": True, "reason": "OK", "updated_at": updated_label,
            "nifty500_change_pct": nifty_change, "nifty500_ltp": live_ltp,
            "nifty500_previous_close": display_close, "nifty500_reference_close": prev_close,
            "closed_session_label": session_label, "closed_session_basis": session_basis,
            "market_close_time": "15:30 IST", "sector_alignment_pct": sector.get("alignment_pct"),
            "sector_complete": bool(sector.get("available")), "sector_coverage": sector.get("coverage", "0/500"),
            "sector_mapped": sector.get("mapped", 0), "sector_priced": sector.get("priced", 0),
            "sector_count": sector.get("sectors", 0), "positive_sectors": sector.get("positive_sectors", 0),
            "negative_sectors": sector.get("negative_sectors", 0), "market_data_source": "DHAN",
            "_cache_date": now.date(), "_cache_mode": cache_key,
        }
        return self._store(result)

    def _store(self, result):
        with self._lock:
            self._cached = result
            self._cached_at = time.monotonic()
        return dict(result)

    @staticmethod
    def _unknown(reason, mode, now, evaluated=0, quotes=None, sector=None):
        sector = sector or {}
        return {
            "universe": "NIFTY 500", "total": 500, "evaluated": int(evaluated), "advances": 0, "declines": 0, "unchanged": 0,
            "ad_ratio": None, "direction": "UNKNOWN", "complete": False, "reason": reason,
            "updated_at": f"Latest completed session • market close 15:30 IST • waiting for Dhan data • refreshed {now.strftime('%H:%M:%S')} IST",
            "nifty500_change_pct": None, "nifty500_ltp": None, "nifty500_previous_close": None, "nifty500_reference_close": None,
            "closed_session_label": "Latest completed NSE session", "closed_session_basis": "waiting for Dhan closed-session data", "market_close_time": "15:30 IST",
            "sector_alignment_pct": sector.get("alignment_pct"), "sector_complete": bool(sector.get("available")),
            "sector_coverage": sector.get("coverage", f"{evaluated}/500"), "sector_mapped": sector.get("mapped", 0),
            "sector_priced": sector.get("priced", 0), "sector_count": sector.get("sectors", 0),
            "positive_sectors": sector.get("positive_sectors", 0), "negative_sectors": sector.get("negative_sectors", 0),
            "market_data_source": "DHAN" if dhan_configured() else "UNCONFIGURED", "_cache_date": now.date(), "_cache_mode": mode,
        }

    def allows(self, side):
        s = self.snapshot(); side = str(side).upper()
        if not s.get("complete") or not s.get("sector_complete"): return False, s
        nifty, sector, ad = s.get("nifty500_change_pct"), s.get("sector_alignment_pct"), s.get("ad_ratio")
        if side == "BUY": return bool(nifty is not None and nifty > 0 and sector is not None and sector > 0 and ad is not None and ad > 1), s
        if side == "SELL": return bool(nifty is not None and nifty < 0 and sector is not None and sector < 0 and ad is not None and ad < 1), s
        return False, s

BREADTH = Nifty500Breadth()
