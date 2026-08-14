"""NIFTY 500 PDH/PDL + Today's Open 1-minute reversal scanner."""

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
from strategy.pdh_pdl_open_cross_engine import PdhPdlOpenCrossEngine


class ScannerEngine:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = PdhPdlOpenCrossEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame()
        self.sectors = pd.DataFrame()
        self.opening_candidates = pd.DataFrame()
        self._prepared_date = None
        self._opening_prepared_date = None
        self.diagnostics = self._empty_diagnostics()

    @staticmethod
    def _empty_diagnostics():
        return {
            "timestamp": None,
            "stocks_scanned": 0,
            "liquidity_passed": 0,
            "opening_level_setup_passed": 0,
            "nifty_alignment_passed": 0,
            "sector_alignment_passed": 0,
            "strategy_setup_passed": 0,
            "stock_alignment_passed": 0,
            "final_signals": 0,
            "rejections": {
                "liquidity": 0,
                "opening_level_setup": 0,
                "nifty_alignment": 0,
                "sector_alignment": 0,
                "pdh_pdl_not_reached": 0,
                "no_open_cross": 0,
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
        root = Path(__file__).resolve().parents[1]
        path = root / "outputs" / "scanner_diagnostics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name("scanner_diagnostics.pdh_pdl.tmp")
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

    def _set_opening_diagnostics(self, references, saved):
        total = len(self.universe) if self.universe is not None else len(references)
        self.diagnostics["stocks_scanned"] = int(total)
        refs = references.copy()
        if refs.empty:
            self.diagnostics["rejections"]["missing_data"] = int(total)
            self._write_diagnostics()
            return
        turnover = pd.to_numeric(refs.get("PreviousDayTurnover"), errors="coerce")
        valid = refs[turnover.notna()].copy()
        missing = max(0, int(total) - len(valid))
        self.diagnostics["rejections"]["missing_data"] = missing
        if valid.empty:
            self._write_diagnostics()
            return
        cutoff = float(turnover.loc[valid.index].median())
        liquidity_passed = int((turnover.loc[valid.index] >= cutoff).sum())
        self.diagnostics["liquidity_passed"] = liquidity_passed
        self.diagnostics["rejections"]["liquidity"] = max(0, len(valid) - liquidity_passed)
        self.diagnostics["opening_level_setup_passed"] = int(len(saved))
        self.diagnostics["rejections"]["opening_level_setup"] = max(0, liquidity_passed - int(len(saved)))
        self._write_diagnostics()

    def prepare_reference_data(self, force=False):
        today = self._today()
        if not force and self._prepared_date == today and not self.references.empty:
            return self.references
        self.universe = self.universe_engine.get_dataframe(refresh=True)
        self.references = ReferenceStore(self.universe).prepare()
        self.sectors = SectorStore(self.universe).prepare()
        self._prepared_date = today
        print("PRE-MARKET NIFTY 500 REFERENCES READY:", len(self.references), "stocks")
        return self.references

    def prepare_opening_candidates(self, force=False):
        today = self._today()
        universe_size = len(self.universe)
        output = Path(__file__).resolve().parents[1] / "outputs" / "references" / f"opening_candidates_nifty500_{universe_size}_{today}.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        required = {"Symbol", "PDH", "PDL", "TodayOpen", "OpeningSetup", "PreviousDayTurnover", "LiquidityQualified"}
        references = self.prepare_reference_data(force=force)
        if not force and self._opening_prepared_date == today and not self.opening_candidates.empty:
            self._set_opening_diagnostics(references, self.opening_candidates)
            return self.opening_candidates
        if not force and output.exists():
            try:
                saved = pd.read_csv(output)
                current_symbols = set(self.universe["Symbol"].astype(str).str.upper())
                saved_symbols = set(saved.get("Symbol", pd.Series(dtype=str)).astype(str).str.upper())
                cache_matches = bool(saved_symbols) and saved_symbols.issubset(current_symbols) and len(saved_symbols) >= int(len(current_symbols) * 0.35)
                if required.issubset(saved.columns) and not saved.empty and cache_matches:
                    self.opening_candidates = saved
                    self._opening_prepared_date = today
                    self._set_opening_diagnostics(references, saved)
                    print("PRE-09:45 NIFTY 500 OPENING CANDIDATES LOADED:", len(saved))
                    return saved
            except Exception as error:
                print("Saved opening candidates could not be loaded:", error)

        if references.empty:
            self.diagnostics["rejections"]["missing_data"] = len(self.universe)
            self._write_diagnostics()
            return pd.DataFrame()

        refs = references.copy()
        refs["PreviousDayTurnover"] = pd.to_numeric(refs["PreviousDayTurnover"], errors="coerce")
        refs["PDH"] = pd.to_numeric(refs["PDH"], errors="coerce")
        refs["PDL"] = pd.to_numeric(refs["PDL"], errors="coerce")
        total = len(refs)
        self.diagnostics["stocks_scanned"] = total
        refs = refs.dropna(subset=["PDH", "PDL", "PreviousDayTurnover"])
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
        print("PRE-09:45 NIFTY 500 LIQUIDITY FILTER:", len(refs), "stocks | cutoff traded value:", round(liquidity_cutoff, 2))

        symbols = refs["Symbol"].astype(str).str.upper().tolist()
        market_data = self.price_data.get_multi_1m(symbols)
        rows = []
        opening_rejected = 0
        for _, ref in refs.iterrows():
            symbol = str(ref["Symbol"]).upper()
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                opening_rejected += 1
                continue
            data = self.price_data.today_only(candles)
            if data is None or data.empty:
                opening_rejected += 1
                continue
            try:
                today_open = float(data.iloc[0]["Open"])
                pdh = float(ref["PDH"])
                pdl = float(ref["PDL"])
            except (TypeError, ValueError):
                opening_rejected += 1
                continue
            if today_open <= 0 or pdh <= 0 or pdl <= 0:
                opening_rejected += 1
                continue

            if today_open > pdh:
                setup = "SELL_PDH_REJECTION"
            elif today_open < pdl:
                setup = "BUY_PDL_REJECTION"
            else:
                opening_rejected += 1
                continue

            rows.append({
                "Symbol": symbol,
                "PDH": round(pdh, 4),
                "PDL": round(pdl, 4),
                "TodayOpen": round(today_open, 4),
                "OpeningSetup": setup,
                "PreviousDayTurnover": round(float(ref["PreviousDayTurnover"]), 2),
                "LiquidityQualified": True,
                "OpenTimestamp": str(data.iloc[0].get("Datetime", "")),
            })

        self.diagnostics["rejections"]["opening_level_setup"] = opening_rejected
        result = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()
        self.diagnostics["opening_level_setup_passed"] = len(result)
        self._write_diagnostics()
        if result.empty:
            print("No NIFTY 500 stocks opened beyond PDH/PDL after liquidity filtering")
            return pd.DataFrame()
        result.to_csv(output, index=False)
        self.opening_candidates = result
        self._opening_prepared_date = today
        print("PRE-09:45 NIFTY 500 OPENING CANDIDATES READY:", len(result))
        return result

    @staticmethod
    def _direction(df):
        if df is None or df.empty:
            return "UNKNOWN"
        data = df.copy()
        if "Datetime" in data.columns:
            data = data.sort_values("Datetime")
        opening = float(data.iloc[0]["Open"])
        close = float(data.iloc[-1]["Close"])
        return "BULLISH" if close > opening else "BEARISH" if close < opening else "NEUTRAL"

    def _market_direction(self):
        return self._direction(self.price_data.get_index_1m("^CNX100"))

    def _sector_directions(self, market_data):
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        rows = []
        for symbol, df in market_data.items():
            if df is None or df.empty:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            direction = self._direction(df)
            if sector != "UNKNOWN" and direction in {"BULLISH", "BEARISH"}:
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
        print("NIFTY 500 PDH/PDL + TODAY OPEN 1-MINUTE OPEN-CROSS SCANNER")
        print("=" * 110)
        self.diagnostics = self._empty_diagnostics()
        self.prepare_reference_data()
        self.diagnostics["stocks_scanned"] = len(self.universe)
        self._write_diagnostics()
        if self.references.empty:
            self.diagnostics["rejections"]["missing_data"] = len(self.universe)
            return self._finish()

        candidates = self.prepare_opening_candidates()
        if candidates.empty:
            return self._finish()

        market_direction = self._market_direction()
        print("NIFTY 100 MARKET BENCHMARK DIRECTION:", market_direction)
        selected = candidates.copy()
        if REQUIRE_MARKET_ALIGNMENT and market_direction in {"BULLISH", "BEARISH"}:
            expected_setup = "BUY_PDL_REJECTION" if market_direction == "BULLISH" else "SELL_PDH_REJECTION"
            selected = selected[selected["OpeningSetup"].eq(expected_setup)].copy()
        self.diagnostics["nifty_alignment_passed"] = len(selected)
        self.diagnostics["rejections"]["nifty_alignment"] = max(0, len(candidates) - len(selected))
        self._write_diagnostics()
        if selected.empty:
            return self._finish()

        symbols = selected["Symbol"].astype(str).str.upper().tolist()
        market_data = self.price_data.get_multi_1m(symbols)
        sector_directions = self._sector_directions(market_data)
        reference_by_symbol = self.references.set_index("Symbol").to_dict("index")
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        signals = []
        sector_passed = 0
        strategy_passed = 0
        stock_passed = 0

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

            signal = self.strategy.build(
                symbol=symbol,
                candles=candles,
                pdh=ref.get("PDH"),
                pdl=ref.get("PDL"),
                today_open=selected.loc[selected["Symbol"].eq(symbol), "TodayOpen"].iloc[0],
                sector_direction=sector_direction,
                nifty_direction=market_direction,
            )
            if not signal:
                self.diagnostics["rejections"]["strategy_setup"] += 1
                continue
            strategy_passed += 1

            if REQUIRE_STOCK_ALIGNMENT and signal.get("stock_today_direction") != signal.get("signal") and signal.get("signal") in {"BUY", "SELL"}:
                self.diagnostics["rejections"]["stock_today_direction"] += 1
                continue
            stock_passed += 1
            signal.update({
                "sector": sector,
                "industry": sector,
                "liquidity_qualified": True,
                "nifty500_universe": True,
            })
            signals.append(signal)
            print("SIGNAL:", symbol, signal["signal"])

        self.diagnostics["sector_alignment_passed"] = sector_passed
        self.diagnostics["strategy_setup_passed"] = strategy_passed
        self.diagnostics["stock_alignment_passed"] = stock_passed
        print("NIFTY 500 FINAL SIGNALS:", len(signals))
        return self._finish(signals)
