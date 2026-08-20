"""Final consistency fixes: complete strategy references and truthful execution diagnostics."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
DIAG = Path("outputs/trade_path_diagnostics.json")


def install(MasterEngine):
    if getattr(MasterEngine, "_trade_path_fix_installed", False): return MasterEngine
    from data.reference_store import ReferenceStore
    original_prepare = ReferenceStore.prepare

    def complete_prepare(self):
        symbols=self.universe["Symbol"].astype(str).str.upper().drop_duplicates().tolist()
        if not symbols:return pd.DataFrame()
        if self.path.exists():
            try:
                saved=pd.read_csv(self.path)
                if len(saved)==len(symbols) and set(saved["Symbol"].astype(str).str.upper())==set(symbols) and self._cached_file_is_valid(saved):return saved
            except Exception:pass
        parts=[];have=set()
        for source_name, loader in [
            ("HISTORICAL_FALLBACK", lambda missing: self._prepare_with_price_data(missing)),
            ("YFINANCE_FALLBACK", lambda missing: self._prepare_with_yfinance(missing)),
            ("DHAN", lambda missing: self._prepare_with_dhan(missing)),
        ]:
            missing=[s for s in symbols if s not in have]
            if not missing:break
            try:
                frame=loader(missing)
                if frame is not None and not frame.empty:
                    frame=frame.drop_duplicates("Symbol").copy();frame["ReferenceSource"]=source_name;parts.append(frame);have|=set(frame["Symbol"].astype(str).str.upper())
            except Exception as exc:
                print(f"Reference source {source_name} failed: {type(exc).__name__}: {exc}")
        if not parts:
            try:return original_prepare(self)
            except Exception:return pd.DataFrame()
        result=pd.concat(parts,ignore_index=True,sort=False)
        priority={"HISTORICAL_FALLBACK":0,"YFINANCE_FALLBACK":1,"DHAN":2}
        result["_priority"]=result["ReferenceSource"].map(priority).fillna(9)
        result["Symbol"]=result["Symbol"].astype(str).str.upper().str.strip()
        result=result.sort_values(["Symbol","_priority"]).drop_duplicates("Symbol").drop(columns=["_priority"])
        result=result[result["Symbol"].isin(set(symbols))].copy()
        if len(result)<len(symbols): return result
        try:return self._save_result(result)
        except Exception as exc:
            print(f"Reference save failed: {type(exc).__name__}: {exc}")
            return result

    ReferenceStore.prepare=complete_prepare
    original_scan=MasterEngine.scan
    def scan_with_truthful_diagnostics(self):
        result=original_scan(self)
        snap=getattr(self,"last_snapshot",{}) or {}
        market_data_ok=bool(snap.get("ad_complete") and snap.get("sector",{}).get("available"))
        gate="BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else "NO_ALIGNMENT"
        reference_count=len(self.references)
        self.diagnostics["market_snapshot"]="PASS" if market_data_ok else "BLOCKED"
        self.diagnostics["market_gate"]=gate
        self.diagnostics["strategy_reference_coverage"]=f"{reference_count}/500"
        self.diagnostics["stocks_scanned"]=reference_count
        if reference_count<500:
            self.diagnostics["rejections"]["strategy_reference"]=f"STRATEGY_REFERENCE_INCOMPLETE_{reference_count}/500"
            result=[]
        self.diagnostics["strategy_market_gate"]="PASS" if market_data_ok and gate!="NO_ALIGNMENT" and reference_count==500 else "BLOCKED"
        self.diagnostics["signals_generated_total"]=int(len(result))
        self.diagnostics["final_signals"]=int(len(result))
        self.diagnostics["signals_by_strategy"]={s:sum(x.get("strategy")==s for x in result) for s in getattr(__import__('strategy.nifty500_price_action_strategies',fromlist=['STRATEGY_DEFINITIONS']),'STRATEGY_DEFINITIONS')}
        try:
            DIAG.parent.mkdir(parents=True,exist_ok=True);data=dict(self.diagnostics);data["worker_status"]="PASS";data["timestamp"]=datetime.now(IST).isoformat(timespec="seconds");DIAG.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        except Exception:pass
        return result
    MasterEngine.scan=scan_with_truthful_diagnostics
    MasterEngine._trade_path_fix_installed=True
    return MasterEngine
