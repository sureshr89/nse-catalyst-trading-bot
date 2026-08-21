"""Reliable daily PDH/PDL/PDC references for the NIFTY-500 strategies."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

from market.price_data import PriceData
from market.dhan_data import dhan_configured, map_nifty500, market_quote

INDIA_TZ = ZoneInfo("Asia/Kolkata")
REQUIRED = 500


class ReferenceStore:
    """Prepare the canonical previous-day and current-open reference set."""

    def __init__(self, universe_df):
        self.universe = universe_df.copy() if universe_df is not None else pd.DataFrame()
        self.folder = Path("outputs") / "open_reversal_references"
        self.folder.mkdir(parents=True, exist_ok=True)

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
        if self.universe.empty or "Symbol" not in self.universe.columns:
            return []
        return list(dict.fromkeys(self._clean_symbol(s) for s in self.universe["Symbol"].dropna()))

    def _coverage(self, df):
        symbols = set(self._symbols())
        if not symbols or df is None or df.empty or "Symbol" not in df.columns:
            return 0.0
        found = {self._clean_symbol(s) for s in df["Symbol"].dropna()}
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
            if low in {"datetime", "date", "timestamp"}:
                rename[c] = "Datetime"
            elif low == "open":
                rename[c] = "Open"
            elif low == "high":
                rename[c] = "High"
            elif low == "low":
                rename[c] = "Low"
            elif low == "close":
                rename[c] = "Close"
            elif low == "volume":
                rename[c] = "Volume"
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
        frame = frame.dropna(subset=required)
        if frame.empty:
            return frame

        frame = frame[
            (frame["Open"] > 0)
            & (frame["High"] >= frame[["Open", "Low", "Close"]].max(axis=1))
            & (frame["Low"] <= frame[["Open", "High", "Close"]].min(axis=1))
        ]
        return frame.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

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
                today_open = float(current.iloc[0]["Open"]) if not current.empty else None

                rows.append(
                    {
                        "Symbol": symbol,
                        "PDH": float(prev["High"]),
                        "PDL": float(prev["Low"]),
                        "PreviousDayClose": float(prev["Close"]),
                        "PreviousDayVolume": float(prev.get("Volume", 0) or 0),
                        "PreviousDayTurnover": float(prev["Close"]) * float(prev.get("Volume", 0) or 0),
                        "TodayOpen": today_open,
                    }
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                continue

        return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()

    def _attach_dhan_open(self, result, symbols):
        """Replace any historical 'today open' with the live Dhan session open."""
        if result.empty or not dhan_configured():
            return result
        try:
            mapping = map_nifty500(symbols, force=False)
            if mapping is None or len(mapping) != len(symbols):
                return result
            quotes = market_quote(mapping, cache_seconds=10)
            if quotes.empty or "TodayOpen" not in quotes.columns:
                return result
            live = quotes[["Symbol", "TodayOpen"]].copy()
            live["Symbol"] = live["Symbol"].map(self._clean_symbol)
            return (
                result.drop(columns=["TodayOpen"], errors="ignore")
                .merge(live, on="Symbol", how="left")
            )
        except Exception:
            return result

    def _save_result(self, result):
        result = result.copy()
        result["Symbol"] = result["Symbol"].map(self._clean_symbol)

        metadata_cols = [c for c in ["Symbol", "Industry", "Sector"] if c in self.universe.columns]
        if "Symbol" in metadata_cols and len(metadata_cols) > 1:
            metadata = self.universe[metadata_cols].copy()
            metadata["Symbol"] = metadata["Symbol"].map(self._clean_symbol)
            result = result.merge(
                metadata.drop_duplicates("Symbol"),
                on="Symbol",
                how="left",
                suffixes=("", "_universe"),
            )
            for c in ["Industry", "Sector"]:
                alt = f"{c}_universe"
                if c not in result.columns and alt in result.columns:
                    result.rename(columns={alt: c}, inplace=True)

        result["PreparedAtIST"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        result["ReferenceCoverage"] = round(self._coverage(result) * 100, 1)
        result.to_csv(self.path, index=False)

        # Gap classification is useful to S1/S3 and is derived from the same
        # canonical PDH/PDL/PDC/open reference set. No signal logic is added here.
        board_cols = {"TodayOpen", "PreviousDayClose", "PDH", "PDL"}
        board = result.dropna(subset=["TodayOpen"]).copy() if "TodayOpen" in result.columns else pd.DataFrame()
        if not board.empty and board_cols.issubset(board.columns):
            board["Gap"] = board["TodayOpen"] - board["PreviousDayClose"]
            board["GapPercent"] = board["Gap"] / board["PreviousDayClose"].replace(0, pd.NA) * 100
            board["GapType"] = board.apply(
                lambda r: "GAP_UP"
                if r["TodayOpen"] > r["PDH"]
                else "GAP_DOWN"
                if r["TodayOpen"] < r["PDL"]
                else "INSIDE_PDH_PDL",
                axis=1,
            )
            board["GapFromPDH_PDL"] = board.apply(
                lambda r: r["TodayOpen"] - r["PDH"]
                if r["GapType"] == "GAP_UP"
                else r["TodayOpen"] - r["PDL"]
                if r["GapType"] == "GAP_DOWN"
                else 0.0,
                axis=1,
            )
            board["GapPercentFromPDH_PDL"] = (
                board["GapFromPDH_PDL"]
                / board["PDH"].where(board["GapType"] == "GAP_UP", board["PDL"]).replace(0, pd.NA)
                * 100
            )
            board.to_csv(Path("outputs") / "gap_analysis.csv", index=False)
        return result

    def _cached_file_is_valid(self, saved):
        required = {
            "Symbol",
            "PDH",
            "PDL",
            "PreviousDayClose",
            "PreviousDayVolume",
            "PreviousDayTurnover",
            "PreparedAtIST",
        }
        if not required.issubset(saved.columns):
            return False
        if len(saved) != len(self._symbols()) or self._coverage(saved) < 1.0:
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
                    # A valid cached file is sufficient pre-open. During market
                    # hours, refresh only the live open when Dhan can verify the
                    # complete quote batch.
                    if dhan_configured():
                        refreshed = self._attach_dhan_open(saved, symbols)
                        if "TodayOpen" in refreshed.columns and refreshed["TodayOpen"].notna().all():
                            return self._save_result(refreshed)
                    return saved
            except Exception:
                pass

        # Historical PDH/PDL/PDC is a batch preparation problem, not 500 live
        # quote requests. Keep it outside the 15-second live-data cycle.
        try:
            result = self._rows_from_daily_map(
                PriceData().get_multi_daily(symbols, period="10d"), symbols
            )
        except Exception:
            result = pd.DataFrame()

        if len(result) != REQUIRED or self._coverage(result) < 1.0:
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
