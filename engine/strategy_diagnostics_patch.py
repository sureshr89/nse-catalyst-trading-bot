"""Deterministic S1-S5 diagnostics using the exact runtime setup predicates."""
from pathlib import Path
import json

DIAG = Path("outputs/trade_path_diagnostics.json")
STRATEGIES = ["S1", "S2", "S3", "S4", "S5"]


def _blank():
    return {s: {"side_gate": 0, "setup_pass": 0, "signal": 0, "risk_or_validation_reject": 0, "last_rejection": None} for s in STRATEGIES}


def _setup(strategy, side, today_open, pdh, pdl, ltp, today_low, today_high, prior_high, prior_low, pullback_low, pullback_high, breakout_seen, pdh_swept, pdl_swept):
    if strategy == "S1":
        if side == "BUY":
            return today_open > pdh and pdh_swept and today_low < pdh
        return today_open < pdl and pdl_swept and today_high > pdl
    if strategy == "S2":
        if side == "BUY":
            return breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh
        return breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl
    if strategy == "S3":
        inside_range = pdl < today_open < pdh
        if side == "BUY":
            return inside_range and pdl_swept and today_low < pdl
        return inside_range and pdh_swept and today_high > pdh
    if strategy == "S4":
        return (prior_high is not None and ltp > prior_high) if side == "BUY" else (prior_low is not None and ltp < prior_low)
    return ltp > pdh if side == "BUY" else ltp < pdl


def install(MasterEngine):
    if getattr(MasterEngine, "_strategy_diagnostics_installed", False):
        return MasterEngine
    original_scan = MasterEngine.scan
    original_eval = MasterEngine._evaluate_stock

    def evaluate_with_counts(self, symbol, ref, d, snap):
        stats = self.diagnostics.setdefault("strategy_diagnostics", _blank())
        if d is None or getattr(d, "empty", True):
            for s in STRATEGIES:
                stats[s]["last_rejection"] = "NO_INTRADAY_DATA"
            return original_eval(self, symbol, ref, d, snap)

        prev = d.iloc[-1]
        dhan = (snap.get("dhan_quotes") or {}).get(str(symbol).upper(), {})
        try:
            today_open = float(dhan.get("TodayOpen") or d.iloc[0]["Open"])
            today_low = float(dhan.get("TodayLow") or d["Low"].min())
            today_high = float(dhan.get("TodayHigh") or d["High"].max())
            ltp = float(dhan.get("LTP") or prev["Close"])
            pdh, pdl = float(ref["PDH"]), float(ref["PDL"])
        except (TypeError, ValueError, KeyError):
            for s in STRATEGIES:
                stats[s]["last_rejection"] = "INVALID_MARKET_DATA"
            return original_eval(self, symbol, ref, d, snap)

        prior = d.iloc[:-1] if len(d) >= 2 else d.iloc[0:0]
        if not prior.empty:
            # Match master_engine: BUY uses PDL sweep, SELL uses PDH sweep.
            pdh_swept = bool((prior["High"] > pdh).any())
            pdl_swept = bool((prior["Low"] < pdl).any())
            breakout_buy = bool((prior["High"] > pdh).any())
            breakout_sell = bool((prior["Low"] < pdl).any())
            prior_high, prior_low = float(prior["High"].max()), float(prior["Low"].min())
            pullback_low, pullback_high = float(prior["Low"].min()), float(prior["High"].max())
        else:
            pdh_swept = pdl_swept = breakout_buy = breakout_sell = False
            prior_high = prior_low = pullback_low = pullback_high = None

        for side in ("BUY", "SELL"):
            # Candle colour is diagnostic only; master_engine no longer hard-blocks on it.
            side_ok = bool((side == "BUY" and snap.get("buy_alignment")) or
                           (side == "SELL" and snap.get("sell_alignment")))
            for strategy in STRATEGIES:
                if not side_ok:
                    stats[strategy]["last_rejection"] = "MASTER_ALIGNMENT_BLOCKED"
                    continue
                stats[strategy]["side_gate"] += 1
                setup = _setup(strategy, side, today_open, pdh, pdl, ltp, today_low, today_high,
                               prior_high, prior_low, pullback_low, pullback_high,
                               breakout_buy if side == "BUY" else breakout_sell,
                               pdh_swept, pdl_swept)
                if setup:
                    stats[strategy]["setup_pass"] += 1
                    stats[strategy]["last_rejection"] = None
                else:
                    stats[strategy]["last_rejection"] = "SETUP_BLOCKED"

        result = original_eval(self, symbol, ref, d, snap)
        for sig in result:
            strategy = str(sig.get("strategy", "")).upper()
            if strategy in stats:
                stats[strategy]["signal"] += 1
                stats[strategy]["last_rejection"] = None
        return result

    def scan_with_diagnostics(self):
        self.diagnostics["strategy_diagnostics"] = _blank()
        self.diagnostics["strategy_stop_reason"] = {}
        result = original_scan(self)
        stats = self.diagnostics["strategy_diagnostics"]
        for s, row in stats.items():
            row["risk_or_validation_reject"] = max(0, row["setup_pass"] - row["signal"])
            if row["signal"] > 0:
                reason = "SIGNAL_GENERATED"
            elif row["setup_pass"] > 0:
                reason = "RISK_OR_VALIDATION_REJECTED"
            elif row["side_gate"] > 0:
                reason = "NO_STOCK_PASSED_SETUP"
            else:
                reason = "MASTER_ALIGNMENT_BLOCKED"
            self.diagnostics["strategy_stop_reason"][s] = reason
        try:
            DIAG.parent.mkdir(parents=True, exist_ok=True)
            DIAG.write_text(json.dumps(dict(self.diagnostics), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
        return result

    MasterEngine._evaluate_stock = evaluate_with_counts
    MasterEngine.scan = scan_with_diagnostics
    MasterEngine._strategy_diagnostics_installed = True
    return MasterEngine
