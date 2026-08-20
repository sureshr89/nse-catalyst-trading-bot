"""Keep trade-path diagnostics synchronized with the authoritative Dhan snapshot."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

IST = ZoneInfo("Asia/Kolkata")
PATH = Path("outputs/trade_path_diagnostics.json")


def install(MasterEngine):
    if getattr(MasterEngine, "_diagnostic_consistency_installed", False):
        return MasterEngine
    original = MasterEngine._market_snapshot

    def snapshot(self):
        snap = original(self)
        self.last_snapshot = snap
        rejections = dict(self.diagnostics.get("rejections") or {})
        market_ok = bool(
            snap.get("ad_complete")
            and snap.get("sector", {}).get("available")
            and snap.get("dhan_quotes")
        )
        buy = bool(snap.get("buy_alignment"))
        sell = bool(snap.get("sell_alignment"))
        reference_count = len(getattr(self, "references", []))
        reference_ok = reference_count == 500
        blocked_reason = snap.get("block_reason")

        if blocked_reason:
            rejections["market_data"] = str(blocked_reason)
        if not market_ok:
            rejections.setdefault("market_data", "AUTHORITATIVE_MARKET_SNAPSHOT_INCOMPLETE")
        if not reference_ok:
            rejections["strategy_reference"] = f"STRATEGY_REFERENCE_INCOMPLETE_{reference_count}/500"

        self.diagnostics["rejections"] = rejections
        self.diagnostics["market_snapshot"] = "PASS" if market_ok else "BLOCKED"
        self.diagnostics["market_gate"] = "BUY" if buy else "SELL" if sell else "NO_ALIGNMENT"
        self.diagnostics["strategy_market_gate"] = (
            "PASS" if market_ok and reference_ok and (buy or sell) else "BLOCKED"
        )
        self.diagnostics["strategy_reference_coverage"] = f"{reference_count}/500"
        self.diagnostics["trade_path_status"] = (
            "READY" if market_ok and reference_ok and (buy or sell) else "BLOCKED"
        )
        self.diagnostics["worker_status"] = (
            "PASS" if market_ok and reference_ok else "BLOCKED"
        )
        self.diagnostics["timestamp"] = datetime.now(IST).isoformat(timespec="seconds")

        PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            PATH.write_text(
                json.dumps(dict(self.diagnostics), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass
        return snap

    MasterEngine._market_snapshot = snapshot
    MasterEngine._diagnostic_consistency_installed = True
    return MasterEngine
