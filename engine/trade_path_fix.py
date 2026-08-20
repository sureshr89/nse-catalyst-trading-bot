"""Final consistency fixes: complete strategy references and truthful execution diagnostics."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
DIAG = Path("outputs/trade_path_diagnostics.json")
REQUIRED = 500


def install(MasterEngine):
    if getattr(MasterEngine, "_trade_path_fix_installed", False):
        return MasterEngine
    from data.reference_store import ReferenceStore
    original_prepare = ReferenceStore.prepare

    def complete_prepare(self):
        symbols = self.universe["Symbol"].astype(str).str.upper().str.strip().drop_duplicates().tolist()
        if len(symbols) != REQUIRED:
            return pd.DataFrame()
        if self.path.exists():
            try:
                saved = pd.read_csv(self.path)
                if (len(saved) == REQUIRED and set(saved["Symbol"].astype(str).str.upper().str.strip()) == set(symbols)
                        and self._cached_file_is_valid(saved)):
                    return saved
            except Exception:
                pass

        parts = []
        have = set()
        # Historical data is authoritative for PDH/PDL/PDC; alternate sources
        # only fill symbols that the preceding source could not supply.
        for source_name, loader in [
            ("HISTORICAL_FALLBACK", lambda missing: self._prepare_with_price_data(missing)),
            ("YFINANCE_FALLBACK", lambda missing: self._prepare_with_yfinance(missing)),
            ("DHAN", lambda missing: self._prepare_with_dhan(missing)),
        ]:
            missing = [s for s in symbols if s not in have]
            if not missing:
                break
            try:
                frame = loader(missing)
                if frame is not None and not frame.empty and "Symbol" in frame.columns:
                    frame = frame.copy()
                    frame["Symbol"] = frame["Symbol"].astype(str).str.upper().str.strip()
                    frame = frame.drop_duplicates("Symbol")
                    frame["ReferenceSource"] = source_name
                    parts.append(frame)
                    have |= set(frame["Symbol"])
            except Exception as exc:
                print(f"Reference source {source_name} failed: {type(exc).__name__}: {exc}")

        if not parts:
            try:
                return original_prepare(self)
            except Exception:
                return pd.DataFrame()

        result = pd.concat(parts, ignore_index=True, sort=False)
        priority = {"HISTORICAL_FALLBACK": 0, "YFINANCE_FALLBACK": 1, "DHAN": 2}
        result["_priority"] = result["ReferenceSource"].map(priority).fillna(9)
        result = result.sort_values(["Symbol", "_priority"]).drop_duplicates("Symbol").drop(columns=["_priority"])
        result = result[result["Symbol"].isin(set(symbols))].copy()

        required_columns = {"Symbol", "PDH", "PDL", "PreviousDayClose"}
        if len(result) != REQUIRED or not required_columns.issubset(result.columns):
            return pd.DataFrame()
        for col in ["PDH", "PDL", "PreviousDayClose"]:
            result[col] = pd.to_numeric(result[col], errors="coerce")
        if result[list(required_columns - {"Symbol"})].isna().any().any():
            return pd.DataFrame()
        if (result[["PDH", "PDL", "PreviousDayClose"]] <= 0).any().any():
            return pd.DataFrame()
        if (result["PDH"] < result["PDL"]).any():
            return pd.DataFrame()
        try:
            return self._save_result(result)
        except Exception as exc:
            print(f"Reference save failed: {type(exc).__name__}: {exc}")
            return result

    ReferenceStore.prepare = complete_prepare
    original_scan = MasterEngine.scan

    def scan_with_truthful_diagnostics(self):
        result = original_scan(self)
        snap = getattr(self, "last_snapshot", {}) or {}
        sector = snap.get("sector") or {}
        verified = bool(snap.get("verified", {}).get("complete"))
        market_data_ok = bool(snap.get("ad_complete") and sector.get("available") and verified)
        gate = "BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else "NO_ALIGNMENT"
        reference_count = len(getattr(self, "references", pd.DataFrame()))

        self.diagnostics["market_snapshot"] = "PASS" if market_data_ok else "BLOCKED"
        self.diagnostics["market_gate"] = gate
        self.diagnostics["strategy_reference_coverage"] = f"{reference_count}/{REQUIRED}"
        self.diagnostics["stocks_scanned"] = reference_count

        if reference_count != REQUIRED:
            self.diagnostics.setdefault("rejections", {})["strategy_reference"] = f"STRATEGY_REFERENCE_INCOMPLETE_{reference_count}/{REQUIRED}"
            result = []

        strategy_gate_ok = market_data_ok and gate != "NO_ALIGNMENT" and reference_count == REQUIRED
        self.diagnostics["strategy_market_gate"] = "PASS" if strategy_gate_ok else "BLOCKED"
        self.diagnostics["signals_generated_total"] = int(len(result))
        self.diagnostics["final_signals"] = int(len(result))
        try:
            from strategy.nifty500_price_action_strategies import STRATEGY_DEFINITIONS
            self.diagnostics["signals_by_strategy"] = {
                s: sum(str(x.get("strategy", "")).upper() == s for x in result)
                for s in STRATEGY_DEFINITIONS
            }
        except Exception:
            self.diagnostics["signals_by_strategy"] = {}
        try:
            DIAG.parent.mkdir(parents=True, exist_ok=True)
            data = dict(self.diagnostics)
            data["worker_status"] = "PASS" if strategy_gate_ok else "BLOCKED"
            data["timestamp"] = datetime.now(IST).isoformat(timespec="seconds")
            DIAG.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
        return result

    MasterEngine.scan = scan_with_truthful_diagnostics
    MasterEngine._trade_path_fix_installed = True
    return MasterEngine
