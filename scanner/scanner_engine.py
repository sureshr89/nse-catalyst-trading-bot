"""NIFTY 100 Gap-Failure + Open-Reclaim scanner with transparent filter diagnostics."""

from pathlib import Path
import json
from datetime import datetime

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
        self.diagnostics = self._empty_diagnostics()

    @staticmethod
    def _empty_diagnostics():
        return {
            "timestamp": None,
            "stocks_scanned": 0,
            "liquidity_passed": 0,
            "gap_previous_day_passed": 0,
            "nifty_alignment_passed": 0,
            "sector_alignment_passed": 0,
            "strategy_setup_passed": 0,
            "stock_alignment_passed": 0,
            "final_signals": 0,
            "rejections": {
                "liquidity": 0,
                "gap_previous_day": 0,
                "nifty_alignment": 0,
                "sector_alignment": 0,
                "no_gap_failure": 0,
                "no_open_reclaim": 0,
                "strategy_setup": 0,
                "stock_alignment": 0,
                "stock_today_direction": 0,
                "missing_data": 0,
            },
        }

    def _write_diagnostics(self):
        payload = dict(self.diagnostics)
        payload["rejections"] = dict(self.diagnostics.get("rejections", {}))
        payload["timestamp"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.diagnostics["timestamp"] = payload["timestamp"]
        # Always write relative to the repository, never the process working directory.
        root = Path(__file__).resolve().parents[1]
        path = root / "outputs" / "scanner_diagnostics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"scanner_diagnostics.{Path(__file__).stem}.tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            temporary.replace(path)
        except Exception as error:
            print("Could not write scanner diagnostics:", error)

    def _finish(self, signals=None):
        self.diagnostics["final_signals"] = len(signals or [])
        self._write_diagnostics()
        return signals or []

    @staticmethod
    def _today():
        return pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")

    def _set_loaded_gap_diagnostics(self, references, saved):
        """Reconstruct filter counts when the pre-market candidate CSV is reused."""
        total = len(self.universe) if self.universe is not None else len(references)
        self.diagnostics["stocks_scanned"] = int(total)
        refs = references.copy()
        if refs.empty:
            self.diagnostics["rejections"]["missing_data"] = int(total)
            self._write_diagnostics()
            return
        turnover = pd.to_numeric(refs.get("PreviousDayTurnover"), errors="coerce")
        pdc = pd.to_numeric(refs.get("PDC"), errors="coerce")
        valid = refs[turnover.notna() & pdc.notna()].copy()
        missing = max(0, int(total) - len(valid))
        self.diagnostics["rejections"]["missing_data"] = missing
        if valid.empty:
            self._write_diagnostics()
            return
        cutoff = float(turnover.loc[valid.index].median())
        liquidity_mask = turnover.loc[valid.index] >= cutoff
        liquidity_passed = int(liquidity_mask.sum())
        self.diagnostics["liquidity_passed"] = liquidity_passed
        self.diagnostics["rejections"]["liquidity"] = max(0, len(valid) - liquidity_passed)
        self.diagnostics["gap_previous_day_passed"] = int(len(saved))
        self.diagnostics["rejections"]["gap_previous_day"] = max(0, liquidity_passed - int(len(saved)))
        self._write_diagnostics()

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
        today = self._today()
        output = Path(__file__).resolve().parents[1] / "outputs" / "references" / f"gap_candidates_{today}.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        required = {
            "Symbol", "PDC", "TodayOpen", "GapPct", "GapDirection",
            "PreviousDayDirection", "PreviousDayTurnover", "LiquidityQualified",
        }
        references = self.prepare_reference_data(force=force)
        if not force and self._gap_prepared_date == today and not self.gap_candidates.empty:
            self._set_loaded_gap_diagnostics(references, self.gap_candidates)
            return self.gap_candidates
        if not force and output.exists():
            try:
                saved = pd.read_csv(output)
                if required.issubset(saved.columns) and not saved.empty:
                    self.gap_candidates = saved
                    self._gap_prepared_date = today
                    self._set_loaded_gap_diagnostics(references, saved)
                    print("PRE-09:45 CANDIDATES LOADED:", len(saved), "stocks")
                    return saved
            except Exception as error:
                print("Saved gap candidates could not be loaded:", error)

        if references.empty:
            print("Cannot prepare candidates: PDC references unavailable")
            self.diagnostics["rejections"]["missing_data"] = len(self.universe)
            self._write_diagnostics()
            return pd.DataFrame()

        refs = references.copy()
        refs["PreviousDayTurnover"] = pd.to_numeric(refs["PreviousDayTurnover"], errors="coerce")
        refs["PDC"] = pd.to_numeric(refs["PDC"], errors="coerce")
        refs["PreviousDayOpen"] = pd.to_numeric(refs["PreviousDayOpen"], errors="coerce")
        total = len(refs)
        self.diagnostics["stocks_scanned"] = total
        refs = refs.dropna(subset=["PDC", "PreviousDayTurnover"])
        if refs.empty:
            self.diagnostics["rejections"]["missing_data"] = total
            self._write_diagnostics()
            return pd.DataFrame()

        self.diagnostics["rejections"]["missing_data"] = max(0, total - len(refs))
        liquidity_cutoff = float(refs["PreviousDayTurnover"].median())
        refs["LiquidityQualified"] = refs["PreviousDayTurnover"] >= liquidity_cutoff
        liquidity_passed = int(refs["LiquidityQualified"].sum())
        self.diagnostics["liquidity_passed"] = liquidity_passed
        self.diagnostics["rejections"]["liquidity"] = max(0, len(refs) - liquidity_passed)
        refs = refs[refs["LiquidityQualified"]].copy()
        print("PRE-09:45 LIQUIDITY FILTER:", len(refs), "stocks | cutoff traded value:", round(liquidity_cutoff, 2))
        self._write_diagnostics()

        symbols = refs["Symbol"].astype(str).str.upper().tolist()
        market_data = self.price_data.get_multi_1m(symbols)
        rows = []
        gap_rejected = 0
        for _, ref in refs.iterrows():
            symbol = str(ref["Symbol"]).upper()
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                gap_rejected += 1
                continue
            data = self.price_data.today_only(candles)
            if data is None or data.empty:
                gap_rejected += 1
                continue
            first = data.iloc[0]
            try:
                today_open = float(first["Open"])
                pdc = float(ref["PDC"])
            except (TypeError, ValueError):
                gap_rejected += 1
                continue
            if today_open <= 0 or pdc <= 0:
                gap_rejected += 1
                continue
            gap_pct = round((today_open - pdc) / pdc * 100.0, 4)
            gap_direction = "GAP_UP" if today_open > pdc else "GAP_DOWN" if today_open < pdc else "FLAT"
            previous_direction = str(ref.get("PreviousDayDirection", "NEUTRAL")).upper()
            if gap_direction == "GAP_UP" and previous_direction != "BULLISH":
                gap_rejected += 1
                continue
            if gap_direction == "GAP_DOWN" and previous_direction != "BEARISH":
                gap_rejected += 1
                continue
            if gap_direction == "FLAT":
                gap_rejected += 1
                continue
            rows.append({
                "Symbol": symbol, "PDC": round(pdc, 4), "TodayOpen": round(today_open, 4),
                "GapPct": gap_pct, "GapDirection": gap_direction,
                "PreviousDayDirection": previous_direction,
                "PreviousDayTurnover": round(float(ref["PreviousDayTurnover"]), 2),
                "LiquidityQualified": True, "OpenTimestamp": str(first.get("Datetime", "")),
            })

        self.diagnostics["rejections"]["gap_previous_day"] = gap_rejected
        result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        self.diagnostics["gap_previous_day_passed"] = len(result)
        self._write_diagnostics()
        if result.empty:
            print("No stocks met liquidity + previous-day direction + opening-gap filters")
            return pd.DataFrame()
        result.to_csv(output, index=False)
        self.gap_candidates = result
        self._gap_prepared_date = today
        print("PRE-09:45 CANDIDATES READY:", len(result))
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
        return "BULLISH" if close > day_open else "BEARISH" if close < day_open else "NEUTRAL"

    def _nifty100_direction(self):
        return self._direction(self.price_data.get_index_1m("^CNX100"))

    def _sector_directions(self, market_data):
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        rows = []
        for symbol, df in market_data.items():
            if df is None or df.empty:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            if sector == "UNKNOWN":
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
        self.diagnostics = self._empty_diagnostics()
        self.prepare_reference_data()
        self.diagnostics["stocks_scanned"] = len(self.universe)
        self._write_diagnostics()
        if self.references.empty:
            self.diagnostics["rejections"]["missing_data"] = len(self.universe)
            return self._finish()

        gap_candidates = self.prepare_gap_candidates()
        if gap_candidates.empty:
            return self._finish()

        nifty_direction = self._nifty100_direction()
        print("NIFTY 100 Direction:", nifty_direction)
        if REQUIRE_MARKET_ALIGNMENT and nifty_direction not in {"BULLISH", "BEARISH"}:
            self.diagnostics["rejections"]["nifty_alignment"] = len(gap_candidates)
            return self._finish()

        selected_gap = "GAP_UP" if nifty_direction == "BULLISH" else "GAP_DOWN"
        selected_symbols = gap_candidates.loc[
            gap_candidates["GapDirection"].astype(str).str.upper() == selected_gap, "Symbol"
        ].astype(str).str.upper().tolist()
        self.diagnostics["nifty_alignment_passed"] = len(selected_symbols)
        self.diagnostics["rejections"]["nifty_alignment"] = max(0, len(gap_candidates) - len(selected_symbols))
        self._write_diagnostics()
        print("PRE-SELECTED", selected_gap, "STOCKS:", len(selected_symbols))
        if not selected_symbols:
            return self._finish()

        market_data = self.price_data.get_multi_1m(selected_symbols)
        sector_directions = self._sector_directions(market_data)
        reference_by_symbol = self.references.set_index("Symbol").to_dict("index")
        signals = []
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        sector_passed_symbols = []
        strategy_passed_symbols = []

        for symbol in selected_symbols:
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                self.diagnostics["rejections"]["missing_data"] += 1
                continue
            ref = reference_by_symbol.get(symbol)
            if not ref:
                self.diagnostics["rejections"]["missing_data"] += 1
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            sector_direction = sector_directions.get(sector, "UNKNOWN")
            if REQUIRE_SECTOR_ALIGNMENT and sector_direction != nifty_direction:
                self.diagnostics["rejections"]["sector_alignment"] += 1
                continue
            sector_passed_symbols.append(symbol)

            signal = self.strategy.build(
                symbol=symbol, candles=candles, pdc=ref.get("PDC"),
                previous_day_open=ref.get("PreviousDayOpen"),
                sector_direction=sector_direction, nifty_direction=nifty_direction,
            )
            if not signal:
                self.diagnostics["rejections"]["strategy_setup"] += 1
                continue
            strategy_passed_symbols.append(symbol)

            previous_day_direction = str(ref.get("PreviousDayDirection", "NEUTRAL")).upper()
            expected_previous = "BULLISH" if signal.get("signal") == "BUY" else "BEARISH"
            if REQUIRE_STOCK_ALIGNMENT and previous_day_direction != expected_previous:
                self.diagnostics["rejections"]["stock_alignment"] += 1
                continue
            if REQUIRE_STOCK_ALIGNMENT and signal.get("stock_today_direction") not in {"BULLISH", "BEARISH"}:
                self.diagnostics["rejections"]["stock_today_direction"] += 1
                continue

            signal.update({
                "sector": sector, "industry": sector,
                "sector_direction": sector_direction, "industry_direction": sector_direction,
                "market_direction": nifty_direction, "nifty100_direction": nifty_direction,
                "stock_previous_day_direction": previous_day_direction,
                "previous_day_direction": previous_day_direction,
                "previous_day_aligned": True, "gap_direction": selected_gap,
                "liquidity_qualified": True,
            })
            signals.append(signal)
            print("SIGNAL:", symbol, signal["signal"])

        self.diagnostics["sector_alignment_passed"] = len(sector_passed_symbols)
        self.diagnostics["strategy_setup_passed"] = len(strategy_passed_symbols)
        self.diagnostics["stock_alignment_passed"] = len(signals)
        print("Final signals:", len(signals))
        return self._finish(signals)
