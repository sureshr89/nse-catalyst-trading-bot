"""Explain why S1-S5 produced no signals without weakening strategy rules."""
from pathlib import Path
import json

DIAG = Path("outputs/trade_path_diagnostics.json")
STRATEGIES = ["S1", "S2", "S3", "S4", "S5"]


def install(MasterEngine):
    if getattr(MasterEngine, "_strategy_diagnostics_installed", False):
        return MasterEngine
    original_scan = MasterEngine.scan
    original_eval = MasterEngine._evaluate_stock

    def evaluate_with_counts(self, symbol, ref, d, snap):
        if d is not None and not getattr(d, "empty", True):
            stats = self.diagnostics.setdefault("strategy_diagnostics", {s: {"side_gate": 0, "setup_pass": 0, "signal": 0, "risk_or_validation_reject": 0} for s in STRATEGIES})
            prev = d.iloc[-1]
            for side in ("BUY", "SELL"):
                side_ok = ((side == "BUY" and snap.get("buy_alignment") and float(prev["Close"]) > float(prev["Open"])) or
                           (side == "SELL" and snap.get("sell_alignment") and float(prev["Close"]) < float(prev["Open"])))
                if not side_ok:
                    continue
                dhan = (snap.get("dhan_quotes") or {}).get(str(symbol).upper(), {})
                today_open = float(dhan.get("TodayOpen") or d.iloc[0]["Open"])
                today_low = float(dhan.get("TodayLow") or d["Low"].min())
                today_high = float(dhan.get("TodayHigh") or d["High"].max())
                ltp = float(dhan.get("LTP") or prev["Close"])
                pdh, pdl = float(ref["PDH"]), float(ref["PDL"])
                prior = d.iloc[:-1] if len(d) >= 2 else d.iloc[0:0]
                if not prior.empty:
                    pdh_swept = bool((prior["Low"] < pdh).any() or (prior["High"] > pdh).any())
                    pdl_swept = bool((prior["Low"] < pdl).any() or (prior["High"] > pdl).any())
                    breakout_seen = bool((prior["High"] > pdh).any()) if side == "BUY" else bool((prior["Low"] < pdl).any())
                    prior_high = float(prior["High"].max())
                    prior_low = float(prior["Low"].min())
                    pullback_low = float(prior["Low"].min())
                    pullback_high = float(prior["High"].max())
                else:
                    pdh_swept = pdl_swept = breakout_seen = False
                    prior_high = prior_low = pullback_low = pullback_high = None
                setup = {
                    "S1": ((today_open > pdh and pdh_swept and ltp >= today_open) if side == "BUY" else (today_open < pdl and pdl_swept and ltp <= today_open)),
                    "S2": ((breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh) if side == "BUY" else (breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl)),
                    "S3": ((today_open > pdl and pdl_swept and ltp >= today_open) if side == "BUY" else (today_open < pdh and pdh_swept and ltp <= today_open)),
                    "S4": ((prior_high is not None and ltp > prior_high) if side == "BUY" else (prior_low is not None and ltp < prior_low)),
                    "S5": ((ltp > pdh) if side == "BUY" else (ltp < pdl)),
                }
                for strategy, ok in setup.items():
                    stats[strategy]["side_gate"] += 1
                    if ok:
                        stats[strategy]["setup_pass"] += 1
        result = original_eval(self, symbol, ref, d, snap)
        stats = self.diagnostics.setdefault("strategy_diagnostics", {s: {"side_gate": 0, "setup_pass": 0, "signal": 0, "risk_or_validation_reject": 0} for s in STRATEGIES})
        for sig in result:
            s = str(sig.get("strategy", "")).upper()
            if s in stats:
                stats[s]["signal"] += 1
        return result

    def scan_with_diagnostics(self):
        self.diagnostics["strategy_diagnostics"] = {s: {"side_gate": 0, "setup_pass": 0, "signal": 0, "risk_or_validation_reject": 0} for s in STRATEGIES}
        result = original_scan(self)
        stats = self.diagnostics["strategy_diagnostics"]
        for s, row in stats.items():
            row["risk_or_validation_reject"] = max(0, row["setup_pass"] - row["signal"])
        self.diagnostics["strategy_stop_reason"] = {
            s: ("NO_STOCK_PASSED_SETUP" if row["setup_pass"] == 0 else "RISK_OR_VALIDATION_REJECTED" if row["signal"] == 0 else "SIGNAL_GENERATED")
            for s, row in stats.items()
        }
        try:
            DIAG.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(self.diagnostics)
            payload["strategy_diagnostics"] = stats
            payload["strategy_stop_reason"] = self.diagnostics["strategy_stop_reason"]
            DIAG.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
        return result

    MasterEngine._evaluate_stock = evaluate_with_counts
    MasterEngine.scan = scan_with_diagnostics
    MasterEngine._strategy_diagnostics_installed = True
    return MasterEngine
