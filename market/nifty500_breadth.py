"""NIFTY 500 breadth and sector alignment using DhanHQ market data."""
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import threading
import time
import pandas as pd
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.dhan_data import configured as dhan_configured, dhan_status, map_nifty500, market_quote, index_quote

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
        u = self.universe_engine.get_dataframe(refresh=False)
        if u is None or u.empty or "Symbol" not in u.columns:
            # Try a fresh download only when the local copy is unavailable.
            u = self.universe_engine.get_dataframe(refresh=True)
        if u is None or u.empty or "Symbol" not in u.columns:
            return pd.DataFrame()
        u = u.copy()
        u["Symbol"] = u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
        u = u.drop_duplicates("Symbol").reset_index(drop=True)
        if len(u) >= 500:
            self._universe = u.head(500).reset_index(drop=True)
        return u.head(500).reset_index(drop=True)

    def _get_mapping(self, symbols):
        now = time.monotonic()
        if not self._mapping.empty and now - self._mapping_at < 3600 and set(self._mapping.Symbol.astype(str).str.upper()) == set(symbols):
            return self._mapping
        self._mapping = map_nifty500(symbols)
        self._mapping_at = now
        return self._mapping

    @staticmethod
    def _closed_session_mode(now):
        t = now.timetz().replace(tzinfo=None)
        return t >= MARKET_CLOSE or t < MARKET_OPEN

    def _fail(self, reason, mode, now, evaluated=0, sector=None, stage=None):
        status = dhan_status()
        actual = status.get("message") or reason
        if stage:
            actual = f"{reason} | {actual}"
        return self._store(self._unknown(actual, mode, now, evaluated, sector=sector))

    def snapshot(self, force=False):
        now = datetime.now(INDIA_TZ)
        closed_mode = self._closed_session_mode(now)
        mode = "closed" if closed_mode else "live"
        mono = time.monotonic()
        with self._lock:
            if not force and self._cached is not None and now.date() == self._cached.get("_cache_date") and mode == self._cached.get("_cache_mode") and mono - self._cached_at < CACHE_SECONDS:
                return dict(self._cached)

        u = self._get_universe()
        if u.empty or "Symbol" not in u.columns:
            return self._fail("NIFTY_500_UNIVERSE_UNAVAILABLE", mode, now)
        symbols = u.Symbol.astype(str).str.upper().str.replace(".NS", "", regex=False).drop_duplicates().tolist()
        if len(symbols) != 500:
            return self._fail(f"NIFTY_500_UNIVERSE_ONLY_{len(symbols)}/500", mode, now, len(symbols))
        if not dhan_configured():
            return self._fail("DHAN_NOT_CONFIGURED", mode, now)

        mapping = self._get_mapping(symbols)
        if len(mapping) != 500:
            return self._fail(f"DHAN_SECURITY_MAPPING_{len(mapping)}/500", mode, now, len(mapping), stage="MAPPING")

        quotes = market_quote(mapping, cache_seconds=10)
        if quotes.empty:
            return self._fail("DHAN_MARKET_DATA_0/500", mode, now, 0, stage="QUOTE")
        if len(quotes) != 500:
            return self._fail(f"DHAN_MARKET_DATA_{len(quotes)}/500", mode, now, len(quotes), stage="QUOTE")

        quotes["LTP"] = pd.to_numeric(quotes["LTP"], errors="coerce")
        quotes["PreviousClose"] = pd.to_numeric(quotes["PreviousClose"], errors="coerce")
        quotes["TodayClose"] = pd.to_numeric(quotes["TodayClose"], errors="coerce")
        quotes["SessionClose"] = quotes["TodayClose"] if closed_mode else quotes["LTP"]
        bad = quotes.SessionClose.isna() | (quotes.SessionClose <= 0)
        if closed_mode:
            quotes.loc[bad, "SessionClose"] = quotes.loc[bad, "LTP"]
        quotes = quotes.dropna(subset=["SessionClose", "PreviousClose"])
        quotes = quotes[(quotes.SessionClose > 0) & (quotes.PreviousClose > 0)]
        if len(quotes) != 500:
            return self._fail(f"DHAN_VALID_PRICE_DATA_{len(quotes)}/500", mode, now, len(quotes), stage="PRICE")

        quotes["change_pct"] = (quotes.SessionClose - quotes.PreviousClose) / quotes.PreviousClose * 100
        advances = int((quotes.change_pct > 0).sum())
        declines = int((quotes.change_pct < 0).sum())
        unchanged = int((quotes.change_pct == 0).sum())
        ad_ratio = float(advances / declines) if declines else float("inf")

        try:
            sm = load_sector_map(u, refresh=False)
            sector = calculate_sector_alignment(quotes[["Symbol", "change_pct"]], sm, "change_pct")
        except Exception as exc:
            sector = {"available": False, "alignment_pct": None, "mapped": 0, "priced": 0, "sectors": 0, "positive_sectors": 0, "negative_sectors": 0, "coverage": "0/500", "error": str(exc)}

        # Dhan Quote APIs are rate-limited to 1 request/second. Allow the stock
        # request to complete before the separate IDX_I request.
        time.sleep(1.1)
        nifty = index_quote("NIFTY 500")
        prev_close = float(nifty.get("PreviousClose") or 0) if nifty else 0.0
        live_ltp = float(nifty.get("LTP") or 0) if nifty else 0.0
        day_close = float(nifty.get("Close") or 0) if nifty else 0.0
        if closed_mode:
            session_close = day_close if day_close > 0 else live_ltp
            nifty_change = ((session_close - prev_close) / prev_close * 100) if prev_close > 0 else None
            display_close = session_close
            label = "Latest completed NSE session"
        else:
            nifty_change = ((live_ltp - prev_close) / prev_close * 100) if prev_close > 0 else None
            display_close = prev_close
            label = "Previous completed NSE session"

        index_ok = bool(display_close and prev_close and nifty_change is not None)
        result = {
            "universe": "NIFTY 500", "total": 500, "evaluated": 500,
            "advances": advances, "declines": declines, "unchanged": unchanged, "ad_ratio": ad_ratio,
            "direction": "BULLISH" if advances > declines else "BEARISH" if declines > advances else "NEUTRAL",
            "complete": True, "reason": "OK" if index_ok else "DHAN_500_QUOTES_OK_INDEX_QUOTE_UNAVAILABLE",
            "updated_at": f"{label} • market close 15:30 IST • refreshed {now.strftime('%H:%M:%S')} IST",
            "nifty500_change_pct": nifty_change, "nifty500_ltp": live_ltp,
            "nifty500_previous_close": display_close if index_ok else None, "nifty500_reference_close": prev_close if index_ok else None,
            "closed_session_label": label, "closed_session_basis": "Dhan completed-session close" if closed_mode else "Dhan live LTP",
            "market_close_time": "15:30 IST", "sector_alignment_pct": sector.get("alignment_pct"),
            "sector_complete": bool(sector.get("available")), "sector_coverage": sector.get("coverage", "0/500"),
            "sector_mapped": sector.get("mapped", 0), "sector_priced": sector.get("priced", 0),
            "sector_count": sector.get("sectors", 0), "positive_sectors": sector.get("positive_sectors", 0),
            "negative_sectors": sector.get("negative_sectors", 0), "market_data_source": "DHAN",
            "_cache_date": now.date(), "_cache_mode": mode,
        }
        return self._store(result)

    def _store(self, result):
        with self._lock:
            self._cached = result
            self._cached_at = time.monotonic()
        return dict(result)

    @staticmethod
    def _unknown(reason, mode, now, evaluated=0, sector=None):
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
        if not s.get("complete") or not s.get("sector_complete"):
            return False, s
        n, sec, ad = s.get("nifty500_change_pct"), s.get("sector_alignment_pct"), s.get("ad_ratio")
        if side == "BUY": return bool(n is not None and n > 0 and sec is not None and sec > 0 and ad is not None and ad > 1), s
        if side == "SELL": return bool(n is not None and n < 0 and sec is not None and sec < 0 and ad is not None and ad < 1), s
        return False, s

BREADTH = Nifty500Breadth()
