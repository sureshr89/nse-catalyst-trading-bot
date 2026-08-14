"""NIFTY 500 scanner for the PDH/PDL + today's Open reversal strategy."""

from datetime import datetime
from pathlib import Path
import json

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
from strategy.open_reversal_engine import OpenReversalEngine


class ScannerEngine:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = OpenReversalEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame()
        self.sectors = pd.DataFrame()
        self.opening_candidates = pd.DataFrame()
        self.gap_analysis = pd.DataFrame()
        self._prepared_date = None
        self._opening_prepared_date = None
        self.diagnostics = self._empty_diagnostics()

    @staticmethod
    def _empty_diagnostics():
        return {
            "timestamp": None, "stocks_scanned": 0, "liquidity_passed": 0,
            "opening_setup_passed": 0, "market_alignment_passed": 0,
            "sector_alignment_passed": 0, "strategy_setup_passed": 0,
            "stock_alignment_passed": 0, "final_signals": 0,
            "gap_up_count": 0, "gap_down_count": 0, "gap_data_count": 0,
            "rejections": {
                "missing_data": 0, "liquidity": 0, "opening_setup": 0,
                "market_alignment": 0, "sector_alignment": 0,
                "pdh_pdl_not_reached": 0, "no_open_cross": 0,
                "strategy_setup": 0, "stock_alignment": 0,
            },
        }

    @staticmethod
    def _today():
        return pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")

    def _write_diagnostics(self):
        payload = dict(self.diagnostics)
        payload["rejections"] = dict(self.diagnostics.get("rejections", {}))
        payload["timestamp"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.diagnostics["timestamp"] = payload["timestamp"]
        path = Path(__file__).resolve().parents[1] / "outputs" / "scanner_diagnostics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name("scanner_diagnostics.tmp")
        try:
            temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            temp.replace(path)
        except Exception as error:
            print("Could not write scanner diagnostics:", error)

    def _write_gap_analysis(self, rows):
        path = Path(__file__).resolve().parents[1] / "outputs" / "gap_analysis.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            frame = pd.DataFrame(rows)
            if frame.empty:
                frame.to_csv(path, index=False)
            else:
                frame.sort_values("GapPercent", ascending=False).to_csv(path, index=False)
        except Exception as error:
            print("Could not write gap analysis:", error)

    def _finish(self, signals=None):
        result = signals or []
        self.diagnostics["final_signals"] = len(result)
        self._write_diagnostics()
        return result

    def prepare_reference_data(self, force=False):
        today = self._today()
        if not force and self._prepared_date == today and not self.references.empty:
            return self.references
        self.universe = self.universe_engine.get_dataframe(refresh=True)
        self.references = ReferenceStore(self.universe).prepare()
        self.sectors = SectorStore(self.universe).prepare(force=force)
        self._prepared_date = today
        print("NIFTY 500 REFERENCES READY:", len(self.references), "stocks")
        return self.references

    def prepare_opening_candidates(self, force=False):
        today = self._today()
        if not force and self._opening_prepared_date == today and not self.opening_candidates.empty:
            return self.opening_candidates

        references = self.prepare_reference_data(force=force)
        if references.empty:
            self.diagnostics["rejections"]["missing_data"] = len(self.universe)
            self._write_diagnostics()
            return pd.DataFrame()

        refs = references.copy()
        for column in ["PreviousDayClose", "PreviousDayTurnover", "PDH", "PDL"]:
            refs[column] = pd.to_numeric(refs[column], errors="coerce")
        total = len(refs)
        refs = refs.dropna(subset=["PDH", "PDL", "PreviousDayClose", "PreviousDayTurnover"])
        self.diagnostics["stocks_scanned"] = len(self.universe)
        self.diagnostics["rejections"]["missing_data"] = max(0, total - len(refs))
        if refs.empty:
            self._write_diagnostics()
            return pd.DataFrame()

        # Liquidity is a trade filter, not a gap-board filter. We first build
        # the gap board for every stock with valid opening/reference data, then
        # apply liquidity to the actual reversal candidate list.
        cutoff = float(refs["PreviousDayTurnover"].median())
        refs["LiquidityQualified"] = refs["PreviousDayTurnover"] >= cutoff
        self.diagnostics["liquidity_passed"] = int(refs["LiquidityQualified"].sum())
        self.diagnostics["rejections"]["liquidity"] = int((~refs["LiquidityQualified"]).sum())

        market_data = self.price_data.get_multi_1m(refs["Symbol"].astype(str).str.upper().tolist())
        rows, gap_rows = [], []
        for _, ref in refs.iterrows():
            symbol = str(ref["Symbol"]).upper()
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                self.diagnostics["rejections"]["missing_data"] += 1
                continue
            today_data = self.price_data.today_only(candles)
            if today_data.empty:
                self.diagnostics["rejections"]["missing_data"] += 1
                continue
            try:
                today_open = float(today_data.iloc[0]["Open"])
                pdc = float(ref["PreviousDayClose"])
                pdh = float(ref["PDH"])
                pdl = float(ref["PDL"])
            except (TypeError, ValueError):
                self.diagnostics["rejections"]["missing_data"] += 1
                continue

            gap_percent = ((today_open - pdc) / pdc * 100.0) if pdc else 0.0
            gap_type = "GAP_UP" if gap_percent > 0 else "GAP_DOWN" if gap_percent < 0 else "FLAT"
            gap_rows.append({
                "Symbol": symbol,
                "PreviousClose": round(pdc, 4),
                "TodayOpen": round(today_open, 4),
                "Gap": round(today_open - pdc, 4),
                "GapPercent": round(gap_percent, 3),
                "GapType": gap_type,
                "PDH": round(pdh, 4),
                "PDL": round(pdl, 4),
                "PreviousDayTurnover": round(float(ref["PreviousDayTurnover"]), 2),
                "LiquidityQualified": bool(ref["LiquidityQualified"]),
                "PreparedAtIST": datetime.now().astimezone().isoformat(timespec="seconds"),
            })

            if not bool(ref["LiquidityQualified"]):
                continue
            if today_open > pdh:
                setup = "SELL_PDH_TO_OPEN"
            elif today_open < pdl:
                setup = "BUY_PDL_TO_OPEN"
            else:
                self.diagnostics["rejections"]["opening_setup"] += 1
                continue

            rows.append({
                "Symbol": symbol, "PDH": round(pdh, 4), "PDL": round(pdl, 4),
                "TodayOpen": round(today_open, 4), "PreviousDayClose": round(pdc, 4),
                "Gap": round(today_open - pdc, 4), "GapPercent": round(gap_percent, 3),
                "GapType": gap_type, "OpeningSetup": setup,
                "PreviousDayTurnover": round(float(ref["PreviousDayTurnover"]), 2),
                "LiquidityQualified": True,
            })

        self.gap_analysis = pd.DataFrame(gap_rows)
        self.diagnostics["gap_data_count"] = len(gap_rows)
        self.diagnostics["gap_up_count"] = int(sum(1 for r in gap_rows if r["GapType"] == "GAP_UP"))
        self.diagnostics["gap_down_count"] = int(sum(1 for r in gap_rows if r["GapType"] == "GAP_DOWN"))
        self._write_gap_analysis(gap_rows)

        result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        self.diagnostics["opening_setup_passed"] = len(result)
        self.opening_candidates = result
        self._opening_prepared_date = today
        self._write_diagnostics()
        return result

    @staticmethod
    def _direction(df):
        if df is None or df.empty:
            return "UNKNOWN"
        data = df.sort_values("Datetime") if "Datetime" in df.columns else df
        opening = float(data.iloc[0]["Open"])
        close = float(data.iloc[-1]["Close"])
        return "BULLISH" if close > opening else "BEARISH" if close < opening else "NEUTRAL"

    def _market_direction(self):
        return self._direction(self.price_data.get_index_1m("^NSEI"))

    def _sector_directions(self, market_data):
        sector_map = dict(zip(self.sectors.get("Symbol", []), self.sectors.get("Sector", []))) if not self.sectors.empty else {}
        rows = []
        for symbol, df in market_data.items():
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            direction = self._direction(df)
            if sector != "UNKNOWN" and direction in {"BULLISH", "BEARISH"}:
                rows.append((sector, direction))
        if not rows:
            return {}
        frame = pd.DataFrame(rows, columns=["Sector", "Direction"])
        result = {}
        for sector, group in frame.groupby("Sector"):
            bull = int((group["Direction"] == "BULLISH").sum())
            bear = int((group["Direction"] == "BEARISH").sum())
            result[sector] = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "NEUTRAL"
        return result

    def scan(self):
        print("=" * 100)
        print("NIFTY 500 PDH/PDL + TODAY OPEN 1-MINUTE REVERSAL SCANNER")
        print("=" * 100)
        self.diagnostics = self._empty_diagnostics()
        self.prepare_reference_data()
        self.diagnostics["stocks_scanned"] = len(self.universe)

        candidates = self.prepare_opening_candidates()
        if candidates.empty:
            return self._finish()

        market_direction = self._market_direction()
        selected = candidates.copy()
        if REQUIRE_MARKET_ALIGNMENT and market_direction in {"BULLISH", "BEARISH"}:
            expected = "BUY_PDL_TO_OPEN" if market_direction == "BULLISH" else "SELL_PDH_TO_OPEN"
            selected = selected[selected["OpeningSetup"].eq(expected)].copy()
        self.diagnostics["market_alignment_passed"] = len(selected)
        self.diagnostics["rejections"]["market_alignment"] = max(0, len(candidates) - len(selected))
        if selected.empty:
            return self._finish()

        symbols = selected["Symbol"].astype(str).str.upper().tolist()
        market_data = self.price_data.get_multi_1m(symbols)
        sector_directions = self._sector_directions(market_data)
        reference_by_symbol = self.references.set_index("Symbol").to_dict("index")
        sector_map = dict(zip(self.sectors.get("Symbol", []), self.sectors.get("Sector", []))) if not self.sectors.empty else {}
        signals = []
        sector_passed = strategy_passed = stock_passed = 0

        for symbol in symbols:
            candles = market_data.get(symbol)
            ref = reference_by_symbol.get(symbol)
            if candles is None or candles.empty or not ref:
                self.diagnostics["rejections"]["missing_data"] += 1
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            sector_direction = sector_directions.get(sector, "UNKNOWN")
            if REQUIRE_SECTOR_ALIGNMENT and sector_direction != market_direction:
                self.diagnostics["rejections"]["sector_alignment"] += 1
                continue
            sector_passed += 1
            today_open = float(selected.loc[selected["Symbol"].eq(symbol), "TodayOpen"].iloc[0])
            signal = self.strategy.build(symbol, candles, ref.get("PDH"), ref.get("PDL"), today_open, sector_direction, market_direction)
            if not signal:
                self.diagnostics["rejections"]["strategy_setup"] += 1
                continue
            strategy_passed += 1
            expected_direction = "BULLISH" if signal.get("signal") == "BUY" else "BEARISH"
            if REQUIRE_STOCK_ALIGNMENT and signal.get("stock_today_direction") != expected_direction:
                self.diagnostics["rejections"]["stock_alignment"] += 1
                continue
            stock_passed += 1
            opening = selected[selected["Symbol"].eq(symbol)].iloc[0]
            signal.update({
                "sector": sector, "industry": sector, "liquidity_qualified": True,
                "nifty500_universe": True, "previous_day_close": opening.get("PreviousDayClose"),
                "gap": opening.get("Gap"), "gap_percent": opening.get("GapPercent"),
                "gap_type": opening.get("GapType"),
            })
            signals.append(signal)

        self.diagnostics["sector_alignment_passed"] = sector_passed
        self.diagnostics["strategy_setup_passed"] = strategy_passed
        self.diagnostics["stock_alignment_passed"] = stock_passed
        return self._finish(signals)
