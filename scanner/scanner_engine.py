"""NIFTY 100 Gap-Failure + Open-Reclaim scanner."""

from pathlib import Path

import pandas as pd

from config.settings import (
    REQUIRE_MARKET_ALIGNMENT,
    REQUIRE_SECTOR_ALIGNMENT,
    REQUIRE_STOCK_ALIGNMENT,
    TRADING_START,
    LAST_ENTRY_TIME,
    RISK_REWARD_RATIO,
)
from data.reference_store import ReferenceStore
from data.sector_store import SectorStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from strategy.gap_reclaim_engine import GapReclaimEngine


class ScannerEngine:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = GapReclaimEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame()
        self.sectors = pd.DataFrame()
        self.gap_candidates = pd.DataFrame()
        self._prepared_date = None
        self._gap_prepared_date = None

    @staticmethod
    def _today():
        return pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")

    def prepare_reference_data(self, force=False):
        today = self._today()
        if not force and self._prepared_date == today and not self.references.empty:
            return self.references
        self.universe = self.universe_engine.get_dataframe(refresh=True)
        self.references = ReferenceStore(self.universe).prepare()
        self.sectors = SectorStore(self.universe).prepare()
        self._prepared_date = today
        print("PRE-MARKET REFERENCES READY:", len(self.references), "stocks")
        return self.references

    def prepare_gap_candidates(self, force=False):
        """Freeze the pre-09:45 candidate pool for the trading day.

        Candidate eligibility is intentionally decided before strategy scanning:
        high liquidity + previous-day direction + today's opening gap direction.
        Liquidity is measured by previous-day traded value (Close * Volume); the
        high-liquidity set is the upper half of the valid NIFTY 100 universe by
        previous-day traded value. A stock must also have a valid 09:15 regular-
        session opening candle. The resulting pool is persisted once per day.
        """
        today = self._today()
        output = Path("outputs") / "references" / f"gap_candidates_{today}.csv"
        required = {
            "Symbol", "PDC", "TodayOpen", "GapPct", "GapDirection",
            "PreviousDayDirection", "PreviousDayTurnover", "LiquidityQualified",
        }
        if not force and self._gap_prepared_date == today and not self.gap_candidates.empty:
            return self.gap_candidates
        if not force and output.exists():
            try:
                saved = pd.read_csv(output)
                if required.issubset(saved.columns) and not saved.empty:
                    self.gap_candidates = saved
                    self._gap_prepared_date = today
                    print("PRE-09:45 CANDIDATES LOADED:", len(saved), "stocks")
                    return saved
            except Exception as error:
                print("Saved gap candidates could not be loaded:", error)

        references = self.prepare_reference_data(force=force)
        if references.empty:
            print("Cannot prepare candidates: PDC references unavailable")
            return pd.DataFrame()

        refs = references.copy()
        refs["PreviousDayTurnover"] = pd.to_numeric(refs["PreviousDayTurnover"], errors="coerce")
        refs["PDC"] = pd.to_numeric(refs["PDC"], errors="coerce")
        refs["PreviousDayOpen"] = pd.to_numeric(refs["PreviousDayOpen"], errors="coerce")
        refs = refs.dropna(subset=["PDC", "PreviousDayTurnover"])
        if refs.empty:
            return pd.DataFrame()

        liquidity_cutoff = float(refs["PreviousDayTurnover"].median())
        refs["LiquidityQualified"] = refs["PreviousDayTurnover"] >= liquidity_cutoff
        refs = refs[refs["LiquidityQualified"]].copy()
        print("PRE-09:45 LIQUIDITY FILTER:", len(refs), "stocks | cutoff traded value:", round(liquidity_cutoff, 2))

        symbols = refs["Symbol"].astype(str).str.upper().tolist()
        market_data = self.price_data.get_multi_1m(symbols)
        rows = []

        for _, ref in refs.iterrows():
            symbol = str(ref["Symbol"]).upper()
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                continue
            data = self.price_data.today_only(candles)
            if data is None or data.empty:
                continue
            first = data.iloc[0]
            try:
                today_open = float(first["Open"])
                pdc = float(ref["PDC"])
            except (TypeError, ValueError):
                continue
            if today_open <= 0 or pdc <= 0:
                continue

            gap_pct = round((today_open - pdc) / pdc * 100.0, 4)
            gap_direction = "GAP_UP" if today_open > pdc else "GAP_DOWN" if today_open < pdc else "FLAT"
            previous_direction = str(ref.get("PreviousDayDirection", "NEUTRAL")).upper()

            # Pre-filter requires yesterday's direction to agree with today's gap.
            # BULLISH yesterday -> today's GAP_UP; BEARISH yesterday -> today's GAP_DOWN.
            if gap_direction == "GAP_UP" and previous_direction != "BULLISH":
                continue
            if gap_direction == "GAP_DOWN" and previous_direction != "BEARISH":
                continue
            if gap_direction == "FLAT":
                continue

            rows.append({
                "Symbol": symbol,
                "PDC": round(pdc, 4),
                "TodayOpen": round(today_open, 4),
                "GapPct": gap_pct,
                "GapDirection": gap_direction,
                "PreviousDayDirection": previous_direction,
                "PreviousDayTurnover": round(float(ref["PreviousDayTurnover"]), 2),
                "LiquidityQualified": True,
                "OpenTimestamp": str(first.get("Datetime", "")),
            })

        result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        if result.empty:
            print("No stocks met liquidity + previous-day direction + opening-gap filters")
            return pd.DataFrame()

        result.to_csv(output, index=False)
        self.gap_candidates = result
        self._gap_prepared_date = today
        up = int((result["GapDirection"] == "GAP_UP").sum())
        down = int((result["GapDirection"] == "GAP_DOWN").sum())
        print("PRE-09:45 CANDIDATES READY:", len(result), "| GAP UP:", up, "| GAP DOWN:", down)
        return result

    @staticmethod
    def _direction(df):
        if df is None or df.empty:
            return "UNKNOWN"
        data = df.copy()
        if "Datetime" in data.columns:
            data = data.sort_values("Datetime")
        if data.empty:
            return "UNKNOWN"
        day_open = float(data.iloc[0]["Open"])
        close = float(data.iloc[-1]["Close"])
        if close > day_open:
            return "BULLISH"
        if close < day_open:
            return "BEARISH"
        return "NEUTRAL"

    def _nifty100_direction(self):
        return self._direction(self.price_data.get_index_1m("^CNX100"))

    def _sector_directions(self, market_data):
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        rows = []
        for symbol, df in market_data.items():
            if df is None or df.empty:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            if not sector or sector == "UNKNOWN":
                continue
            direction = self._direction(df)
            if direction in {"BULLISH", "BEARISH"}:
                rows.append((sector, direction))
        if not rows:
            return {}
        frame = pd.DataFrame(rows, columns=["Sector", "Direction"])
        result = {}
        for sector, group in frame.groupby("Sector"):
            bullish = int((group["Direction"] == "BULLISH").sum())
            bearish = int((group["Direction"] == "BEARISH").sum())
            result[sector] = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "NEUTRAL"
        return result

    def scan(self):
        print("=" * 110)
        print("NIFTY 100 GAP-FAILURE + OPEN-RECLAIM PRICE-ACTION SCANNER")
        print("=" * 110)
        self.prepare_reference_data()
        if self.references.empty:
            print("No pre-market reference data. No trades.")
            return []

        gap_candidates = self.prepare_gap_candidates()
        if gap_candidates.empty:
            print("No pre-09:45 candidate data. No trades.")
            return []

        nifty_direction = self._nifty100_direction()
        print("NIFTY 100 Direction:", nifty_direction)
        if REQUIRE_MARKET_ALIGNMENT and nifty_direction not in {"BULLISH", "BEARISH"}:
            print("NIFTY 100 is neutral/unavailable. No new trades.")
            return []

        selected_gap = "GAP_UP" if nifty_direction == "BULLISH" else "GAP_DOWN"
        selected_symbols = gap_candidates.loc[
            gap_candidates["GapDirection"].astype(str).str.upper() == selected_gap, "Symbol"
        ].astype(str).str.upper().tolist()
        print("PRE-SELECTED", selected_gap, "STOCKS:", len(selected_symbols))
        if not selected_symbols:
            return []

        market_data = self.price_data.get_multi_1m(selected_symbols)
        sector_directions = self._sector_directions(market_data)
        reference_by_symbol = self.references.set_index("Symbol").to_dict("index")
        signals = []
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}

        for symbol in selected_symbols:
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                continue
            ref = reference_by_symbol.get(symbol)
            if not ref:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            sector_direction = sector_directions.get(sector, "UNKNOWN")
            if REQUIRE_SECTOR_ALIGNMENT and sector_direction not in {"BULLISH", "BEARISH"}:
                continue

            previous_day_direction = str(ref.get("PreviousDayDirection", "NEUTRAL")).upper()
            signal = self.strategy.build(
                symbol=symbol,
                candles=candles,
                pdc=ref.get("PDC"),
                previous_day_open=ref.get("PreviousDayOpen"),
                sector_direction=sector_direction,
                nifty_direction=nifty_direction,
            )
            if not signal:
                continue

            expected_previous = "BULLISH" if signal.get("signal") == "BUY" else "BEARISH"
            previous_day_aligned = previous_day_direction == expected_previous
            if REQUIRE_STOCK_ALIGNMENT and not previous_day_aligned:
                print("REJECT:", symbol, "previous-day stock alignment mismatch")
                continue
            if REQUIRE_STOCK_ALIGNMENT and signal.get("stock_today_direction") not in {"BULLISH", "BEARISH"}:
                continue

            signal["sector"] = sector
            signal["industry"] = sector
            signal["sector_direction"] = sector_direction
            signal["industry_direction"] = sector_direction
            signal["market_direction"] = nifty_direction
            signal["nifty100_direction"] = nifty_direction
            signal["stock_previous_day_direction"] = previous_day_direction
            signal["previous_day_direction"] = previous_day_direction
            signal["previous_day_aligned"] = previous_day_aligned
            signal["gap_direction"] = selected_gap
            signal["liquidity_qualified"] = True
            signals.append(signal)
            print(
                "SIGNAL:", symbol, signal["signal"],
                "Entry", signal["entry"], "SL", signal["stop_loss"],
                "Target", signal["target"], "PDC", signal["pdc"],
                "Gap", selected_gap, "Previous Day", previous_day_direction,
                "Sector", sector_direction, "NIFTY 100", nifty_direction,
            )

        print("Final signals:", len(signals))
        return signals
