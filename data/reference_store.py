"""Reliable daily PDH/PDL/PDC references for the NIFTY-500 strategies.

Historical references are batch-loaded first; Dhan is used for live today's
open when available.  We deliberately require the complete 500-stock set
before returning references to the master strategy gate.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

from market.price_data import PriceData
from market.dhan_data import configured as dhan_configured, map_nifty500, market_quote

INDIA_TZ = ZoneInfo("Asia/Kolkata")
REQUIRED = 500


class ReferenceStore:
    def __init__(self, universe_df):
        self.universe = universe_df.copy()
        self.folder = Path("outputs") / "open_reversal_references"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.minimum_coverage = 1.0
        self.fallback_coverage = 1.0

    @property
    def date_key(self):
        return datetime.now(INDIA_TZ).strftime("%Y-%m-%d")

    @property
    def path(self):
        return self.folder / f"nifty500_open_reversal_{self.date_key}.csv"

    @staticmethod
    def _clean_symbol(symbol):
        return str(symbol).strip().upper().replace(".NS", "")

    def _symbols(self):
        if self.universe is None or self.universe.empty or "Symbol" not in self.universe.columns:
            return []
        return list(dict.fromkeys(self._clean_symbol(s) for s in self.universe["Symbol"]))

    def _coverage(self, df):
        symbols = set(self._symbols())
        if not symbols or df is None or df.empty or "Symbol" not in df.columns:
            return 0.0
        found = {self._clean_symbol(s) for s in df["Symbol"]}
        return len(symbols & found) / len(symbols)

    def _normalise_daily(self, data):
        if data is None or data.empty:
            return pd.DataFrame()
        frame = data.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = [c[0] if isinstance(c, tuple) else c for c in frame.columns]
        if "Datetime" not in frame.columns:
            frame = frame.reset_index()
        rename = {}
        for c in frame.columns:
            low = str(c).strip().lower()
            if low in {"datetime", "date"}: rename[c] = "Datetime"
            elif low == "open": rename[c] = "Open"
            elif low == "high": rename[c] = "High"
            elif low == "low": rename[c] = "Low"
            elif low == "close": rename[c] = "Close"
            elif low == "volume": rename[c] = "Volume"
        frame = frame.rename(columns=rename)
        required = ["Datetime", "Open", "High", "Low", "Close"]
        if any(c not in frame.columns for c in required):
            return pd.DataFrame()
        dates = pd.to_datetime(frame["Datetime"], errors="coerce")
        try:
            dates = dates.dt.tz_localize(INDIA_TZ) if dates.dt.tz is None else dates.dt.tz_convert(INDIA_TZ)
        except Exception:
            return pd.DataFrame()
        frame["Datetime"] = dates
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in frame.columns:
                frame[c] = pd.to_numeric(frame[c], errors="coerce")
        return frame.dropna(subset=required).sort_values("Datetime").reset_index(drop=True)

    def _rows_from_daily_map(self, daily_map, symbols):
        today = datetime.now(INDIA_TZ).date()
        rows = []
        normalised = {self._clean_symbol(k): v for k, v in (daily_map or {}).items()}
        for symbol in symbols:
            try:
                data = self._normalise_daily(normalised.get(symbol))
                if data.empty:
                    continue
                previous = data[data["Datetime"].dt.date < today]
                if previous.empty:
                    continue
                prev = previous.iloc[-1]
                current = data[data["Datetime"].dt.date == today]
                rows.append({
                    "Symbol": symbol,
                    "PDH": float(prev["High"]),
                    "PDL": float(prev["Low"]),
                    "PreviousDayClose": float(prev["Close"]),
                    "PreviousDayVolume": float(prev.get("Volume", 0) or 0),
                    "PreviousDayTurnover": float(prev["Close"]) * float(prev.get("Volume", 0) or 0),
                    "TodayOpen": float(current.iloc[0]["Open"]) if not current.empty else None,
                })
            except Exception:
                continue
        return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()

    def _attach_dhan_open(self, result, symbols):
        if result.empty or not dhan_configured():
            return result
        try:
            mapping = map_nifty500(symbols, force=False)
            if len(mapping) != len(symbols):
                return result
            quotes = market_quote(mapping, cache_seconds=10)
            if quotes.empty:
                return result
            live = quotes[[c for c in ["Symbol", "TodayOpen"] if c in quotes.columns]].copy()
            live["Symbol"] = live["Symbol"].map(self._clean_symbol)
            result = result.drop(columns=["TodayOpen"], errors="ignore").merge(live, on="Symbol", how="left")
        except Exception:
            pass
        return result

    def _save_result(self, result):
        result = result.copy()
        result["Symbol"] = result["Symbol"].map(self._clean_symbol)
        metadata = [c for c in ["Symbol", "Industry", "Sector"] if c in self.universe.columns]
        if len(metadata) >= 2:
            result = result.merge(self.universe[metadata].drop_duplicates("Symbol"), on="Symbol", how="left", suffixes=("", "_universe"))
            for c in ["Industry", "Sector"]:
                alt = f"{c}_universe"
                if c not in result.columns and alt in result.columns:
                    result.rename(columns={alt: c}, inplace=True)
        result["PreparedAtIST"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result["ReferenceCoverage"] = round(self._coverage(result) * 100, 1)
        result.to_csv(self.path, index=False)
        board = result.dropna(subset=["TodayOpen"]).copy() if "TodayOpen" in result.columns else pd.DataFrame()
        if not board.empty and {"TodayOpen", "PreviousDayClose", "PDH", "PDL"}.issubset(board.columns):
            board["Gap"] = board["TodayOpen"] - board["PreviousDayClose"]
            board["GapPercent"] = board["Gap"] / board["PreviousDayClose"] * 100
            board["GapType"] = board.apply(lambda r: "GAP_UP" if r["TodayOpen"] > r["PDH"] else "GAP_DOWN" if r["TodayOpen"] < r["PDL"] else "INSIDE_PDH_PDL", axis=1)
            board["GapFromPDH_PDL"] = board.apply(lambda r: r["TodayOpen"] - r["PDH"] if r["GapType"] == "GAP_UP" else r["TodayOpen"] - r["PDL"] if r["GapType"] == "GAP_DOWN" else 0.0, axis=1)
            board["GapPercentFromPDH_PDL"] = board["GapFromPDH_PDL"] / board["PDH"].where(board["GapType"] == "GAP_UP", board["PDL"]) * 100
            board.to_csv(Path("outputs") / "gap_analysis.csv", index=False)
        return result

    def _cached_file_is_valid(self, saved):
        required = {"Symbol", "PDH", "PDL", "PreviousDayClose", "PreviousDayVolume", "PreviousDayTurnover", "PreparedAtIST"}
        if not required.issubset(saved.columns) or len(saved) != len(self._symbols()) or self._coverage(saved) < 1.0:
            return False
        try:
            prepared = pd.to_datetime(saved["PreparedAtIST"], errors="coerce")
            prepared = prepared.dt.tz_localize(INDIA_TZ) if prepared.dt.tz is None else prepared.dt.tz_convert(INDIA_TZ)
            return prepared.notna().all() and prepared.dt.date.eq(datetime.now(INDIA_TZ).date()).all()
        except Exception:
            return False

    def prepare(self):
        symbols = self._symbols()
        if len(symbols) != REQUIRED:
            return pd.DataFrame()

        if self.path.exists():
            try:
                saved = pd.read_csv(self.path)
                if self._cached_file_is_valid(saved):
                    return saved
            except Exception:
                pass

        # Historical PDH/PDL/PDC is a batch problem, not 500 individual Dhan
        # historical requests. This avoids Dhan rate limits and partial sets.
        try:
            result = self._rows_from_daily_map(PriceData().get_multi_daily(symbols, period="10d"), symbols)
        except Exception:
            result = pd.DataFrame()

        if len(result) != REQUIRED or self._coverage(result) < 1.0:
            # Only use Dhan's per-security historical endpoint as a last resort.
            # The normal path above is deliberately batch based.
            try:
                from market.dhan_data import previous_day_references
                mapping = map_nifty500(symbols, force=False) if dhan_configured() else pd.DataFrame()
                dhan_refs = previous_day_references(mapping) if len(mapping) == REQUIRED else pd.DataFrame()
                if self._coverage(dhan_refs) > self._coverage(result):
                    result = dhan_refs
            except Exception:
                pass

        if len(result) != REQUIRED or self._coverage(result) < 1.0:
            return pd.DataFrame()

        result = self._attach_dhan_open(result, symbols)
        return self._save_result(result)

    def load(self):
        return self.prepare()
