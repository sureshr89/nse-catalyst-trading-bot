"""Make Dhan the single authoritative live data source for price, A/D, sectors and S1-S5 gating."""
from datetime import datetime
import threading
import time
import pandas as pd

_QUOTE_LOCK = threading.RLock()
_QUOTE_CACHE = None
_QUOTE_CACHE_AT = 0.0
_QUOTE_CACHE_KEY = None
QUOTE_CACHE_SECONDS = 8.0


def _dhan_market_quote(mapping, cache_seconds=QUOTE_CACHE_SECONDS):
    """Fetch the exact Dhan quote snapshot and derive previous close from net_change.

    Dhan documents net_change as the absolute LTP change from the previous-day
    closing price. Therefore PreviousClose = LTP - net_change. This is the
    authoritative price basis for stock values, A/D and sector calculations.
    """
    global _QUOTE_CACHE, _QUOTE_CACHE_AT, _QUOTE_CACHE_KEY
    from market.dhan_data import configured, _post

    if mapping is None or mapping.empty or not configured():
        return pd.DataFrame()

    ids = pd.to_numeric(mapping["SecurityId"], errors="coerce").dropna().astype(int).astype(str).tolist()
    expected_ids = set(ids)
    expected_symbols = set(mapping["Symbol"].astype(str).str.upper().str.strip())
    cache_key = tuple(sorted(expected_ids))
    now = time.monotonic()

    with _QUOTE_LOCK:
        if (_QUOTE_CACHE is not None and _QUOTE_CACHE_KEY == cache_key
                and now - _QUOTE_CACHE_AT <= cache_seconds):
            return _QUOTE_CACHE.copy()

    response = _post("/marketfeed/quote", {"NSE_EQ": [int(x) for x in ids]})
    data = response.get("data", {}).get("NSE_EQ", {}) if response else {}
    by_id = dict(zip(mapping["SecurityId"].astype(str), mapping["Symbol"].astype(str).str.upper().str.strip()))
    rows = []

    for sid, item in data.items():
        if str(sid) not in expected_ids or not isinstance(item, dict):
            continue
        ohlc = item.get("ohlc") or {}
        try:
            ltp = float(item.get("last_price") or 0)
            net_change = float(item.get("net_change") or 0)
            day_open = float(ohlc.get("open") or 0)
            day_high = float(ohlc.get("high") or 0)
            day_low = float(ohlc.get("low") or 0)
            day_close = float(ohlc.get("close") or 0)
            volume = float(item.get("volume") or 0)
            if ltp <= 0:
                continue

            previous_close = ltp - net_change
            if previous_close <= 0:
                continue

            # During the live session LTP is the current session value. The
            # Dhan OHLC close is retained separately and is not confused with
            # previous close. PreviousClose comes only from net_change.
            rows.append({
                "Symbol": by_id[str(sid)],
                "SecurityId": str(sid),
                "LTP": ltp,
                "TodayOpen": day_open,
                "TodayHigh": day_high,
                "TodayLow": day_low,
                "TodayClose": day_close,
                "PreviousClose": previous_close,
                "NetChange": net_change,
                "Volume": volume,
                "change_pct": (ltp - previous_close) / previous_close * 100.0,
                "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
                "price_source": "DHAN_MARKETFEED_QUOTE",
            })
        except (TypeError, ValueError):
            continue

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result = result.drop_duplicates("SecurityId")
    returned_ids = set(result["SecurityId"].astype(str))
    returned_symbols = set(result["Symbol"].astype(str).str.upper())
    verified = (
        len(result) == len(expected_ids)
        and returned_ids == expected_ids
        and returned_symbols == expected_symbols
        and result["LTP"].notna().all()
        and result["PreviousClose"].notna().all()
        and (result["LTP"] > 0).all()
        and (result["PreviousClose"] > 0).all()
    )
    if not verified:
        return pd.DataFrame()

    with _QUOTE_LOCK:
        _QUOTE_CACHE = result.copy()
        _QUOTE_CACHE_AT = time.monotonic()
        _QUOTE_CACHE_KEY = cache_key
    return result


def install(MasterEngine):
    """Install one authoritative Dhan snapshot for the entire decision chain."""
    from market import dhan_data
    from market import nifty500_breadth

    # Patch both module references because breadth imported market_quote directly.
    dhan_data.market_quote = _dhan_market_quote
    nifty500_breadth.market_quote = _dhan_market_quote

    def aligned_snapshot(self):
        from market.nifty500_breadth import BREADTH

        # IMPORTANT: do not call the old MasterEngine snapshot here. That path
        # can pull Yahoo data and produce a second, conflicting market snapshot.
        verified = BREADTH.snapshot(force=False)
        if not verified.get("complete") or not verified.get("sector_complete"):
            self.diagnostics["market_data_source"] = "DHAN_VERIFICATION_FAILED"
            self.diagnostics["market_data_coverage"] = f"{verified.get('evaluated', 0)}/500"
            self.diagnostics["ad_coverage"] = f"{verified.get('evaluated', 0)}/500"
            return {
                "intraday": {}, "prices": pd.DataFrame(), "sector": {},
                "nifty_change": None, "ad_ratio": None, "ad_complete": False,
                "buy_alignment": False, "sell_alignment": False, "dhan_quotes": {},
            }

        quotes = verified.get("quote_rows")
        if not isinstance(quotes, pd.DataFrame) or len(quotes) != 500:
            self.diagnostics["market_data_source"] = "DHAN_VERIFICATION_FAILED"
            return {
                "intraday": {}, "prices": pd.DataFrame(), "sector": {},
                "nifty_change": None, "ad_ratio": None, "ad_complete": False,
                "buy_alignment": False, "sell_alignment": False, "dhan_quotes": {},
            }

        # The exact same 500 Dhan LTP/PreviousClose values drive both A/D and sectors.
        prices = quotes[["Symbol", "LTP", "PreviousClose", "NetChange", "change_pct"]].copy()
        prices["LTP"] = pd.to_numeric(prices["LTP"], errors="coerce")
        prices["PreviousClose"] = pd.to_numeric(prices["PreviousClose"], errors="coerce")
        prices["change_pct"] = (prices["LTP"] - prices["PreviousClose"]) / prices["PreviousClose"] * 100.0

        sector = {
            "available": True,
            "mapped": int(verified.get("sector_mapped", 0) or 0),
            "priced": int(verified.get("sector_priced", 0) or 0),
            "coverage": str(verified.get("sector_coverage", "0/500")),
            "alignment_pct": verified.get("sector_alignment_pct"),
            "positive_sectors": int(verified.get("positive_sectors", 0) or 0),
            "negative_sectors": int(verified.get("negative_sectors", 0) or 0),
            "unchanged_sectors": int(verified.get("unchanged_sectors", 0) or 0),
            "sectors": int(verified.get("sector_count", 0) or 0),
        }
        nifty_change = verified.get("nifty500_change_pct")
        ad_ratio = verified.get("ad_ratio")
        sector_change = sector["alignment_pct"]
        buy = bool(nifty_change is not None and nifty_change > 0 and sector_change is not None and sector_change > 0 and ad_ratio is not None and ad_ratio > 1)
        sell = bool(nifty_change is not None and nifty_change < 0 and sector_change is not None and sector_change < 0 and ad_ratio is not None and ad_ratio < 1)

        dhan_quotes = {str(r["Symbol"]).upper().strip(): r for r in quotes.to_dict("records")}

        # Strategy still gets completed 1-minute candles as confirmation, but
        # all master prices, A/D, sector alignment and live entry/exit values
        # come from the same Dhan snapshot.
        symbols = list(dhan_quotes.keys())
        try:
            intraday = self.price_data.get_multi_1m(symbols)
        except Exception:
            intraday = {}

        self.diagnostics.update({
            "market_data_source": "DHAN_VERIFIED_500",
            "market_data_coverage": "500/500",
            "nifty500_change_pct": nifty_change,
            "sector_change_pct": sector_change,
            "sector_available": True,
            "sector_mapping": f"{sector['mapped']}/500",
            "sector_priced": f"{sector['priced']}/500",
            "ad_ratio": ad_ratio,
            "ad_advances": int(verified.get("advances", 0) or 0),
            "ad_declines": int(verified.get("declines", 0) or 0),
            "ad_coverage": "500/500",
            "buy_alignment": buy,
            "sell_alignment": sell,
        })

        return {
            "intraday": intraday,
            "prices": prices,
            "sector": sector,
            "nifty_change": float(nifty_change) if nifty_change is not None else None,
            "ad_ratio": float(ad_ratio) if ad_ratio is not None else None,
            "ad_complete": True,
            "buy_alignment": buy,
            "sell_alignment": sell,
            "dhan_quotes": dhan_quotes,
        }

    MasterEngine._market_snapshot = aligned_snapshot
    MasterEngine._live_data_alignment_patch_installed = True
    return MasterEngine
