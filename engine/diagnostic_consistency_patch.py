"""Keep trade-path diagnostics synchronized with the authoritative Dhan snapshot."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

IST=ZoneInfo("Asia/Kolkata"); PATH=Path("outputs/trade_path_diagnostics.json")

def install(MasterEngine):
    if getattr(MasterEngine,"_diagnostic_consistency_installed",False): return MasterEngine
    original=MasterEngine._market_snapshot
    def snapshot(self):
        snap=original(self)
        self.last_snapshot=snap
        self.diagnostics.setdefault("rejections",{})
        self.diagnostics["rejections"]={}
        market_ok=bool(snap.get("ad_complete") and snap.get("sector",{}).get("available"))
        buy=bool(snap.get("buy_alignment")); sell=bool(snap.get("sell_alignment"))
        self.diagnostics["market_snapshot"]="PASS" if market_ok else "BLOCKED"
        self.diagnostics["market_gate"]="BUY" if buy else "SELL" if sell else "NO_ALIGNMENT"
        self.diagnostics["strategy_market_gate"]="PASS" if market_ok and (buy or sell) else "BLOCKED"
        self.diagnostics["strategy_reference_coverage"]=f"{len(getattr(self,'references',[]))}/500"
        if len(getattr(self,"references",[]))<500:
            self.diagnostics["rejections"]["strategy_reference"]=f"STRATEGY_REFERENCE_INCOMPLETE_{len(self.references)}/500"
        PATH.parent.mkdir(parents=True,exist_ok=True)
        data=dict(self.diagnostics); data["worker_status"]="PASS"; data["timestamp"]=datetime.now(IST).isoformat(timespec="seconds")
        try: PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        except Exception: pass
        return snap
    MasterEngine._market_snapshot=snapshot; MasterEngine._diagnostic_consistency_installed=True; return MasterEngine
