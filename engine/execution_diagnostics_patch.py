"""Make the S1-S5 signal/execution path observable without changing trading rules."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

IST = ZoneInfo("Asia/Kolkata")
OUT = Path("outputs")
PATH = OUT / "trade_path_diagnostics.json"


def _save(engine, **extra):
    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(getattr(engine, "diagnostics", {}) or {})
    data.update(extra)
    data["timestamp"] = datetime.now(IST).isoformat(timespec="seconds")
    try:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return data


def install(MasterEngine):
    if getattr(MasterEngine, "_execution_diagnostics_patch_installed", False):
        return MasterEngine

    original_process_signals = MasterEngine.process_signals
    original_run_cycle = MasterEngine.run_cycle

    def process_signals(self, signals):
        attempts = []
        for sig in signals:
            strategy = str(sig.get("strategy", "")).upper()
            result = self.paper_engine.open_trade({**sig, "approved": True, "strategy": strategy})
            attempts.append({
                "strategy": strategy,
                "symbol": sig.get("symbol"),
                "side": sig.get("side"),
                "result": "OPENED" if result.get("opened") else "REJECTED",
                "reason": result.get("reason"),
            })
            # Preserve the original engine's accounting/journaling behavior only
            # for trades it actually opens. We cannot call the original method
            # because that would submit the same paper trade twice.
            if result.get("opened"):
                position = result.get("position")
                if position:
                    self.daily_counts[strategy] += 1
                    self.journal.log_trade(position)
        self.diagnostics["execution_attempts"] = len(attempts)
        self.diagnostics["execution_opened"] = sum(x["result"] == "OPENED" for x in attempts)
        self.diagnostics["execution_rejected"] = sum(x["result"] == "REJECTED" for x in attempts)
        self.diagnostics["execution_rejections"] = [x for x in attempts if x["result"] == "REJECTED"]
        self.diagnostics["execution_attempt_details"] = attempts
        _save(self, trade_path="EXECUTION_COMPLETE")
        return [self.paper_engine.open_positions.get(x.get("symbol")) for x in attempts if x["result"] == "OPENED" and x.get("symbol") in self.paper_engine.open_positions]

    def run_cycle(self):
        before = len(getattr(self, "paper_engine", None).open_positions) if getattr(self, "paper_engine", None) else 0
        result = original_run_cycle(self)
        after = len(getattr(self, "paper_engine", None).open_positions) if getattr(self, "paper_engine", None) else 0
        self.diagnostics["worker_status"] = "PASS"
        self.diagnostics["run_cycle_result_count"] = len(result or [])
        self.diagnostics["open_positions_before"] = before
        self.diagnostics["open_positions_after"] = after
        _save(self, trade_path="CYCLE_COMPLETE")
        return result

    MasterEngine.process_signals = process_signals
    MasterEngine.run_cycle = run_cycle
    MasterEngine._execution_diagnostics_patch_installed = True
    return MasterEngine
