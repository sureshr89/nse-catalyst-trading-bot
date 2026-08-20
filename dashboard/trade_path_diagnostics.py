"""Live execution-path diagnostics for the paper trading dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
OUT = Path("outputs")
PATH = OUT / "trade_path_diagnostics.json"


def write(**data):
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(IST).isoformat(timespec="seconds"), **data}
    try:
        PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return payload


def run(engine):
    """Run one scan and expose every gate without bypassing any rule."""
    result = {
        "worker": "RUNNING",
        "market_snapshot": "WAITING",
        "market_gate": "WAITING",
        "stocks_scanned": 0,
        "strategy_candidates": {s: 0 for s in ["S1", "S2", "S3", "S4", "S5"]},
        "signals_generated": 0,
        "signals_selected": 0,
        "execution_attempts": 0,
        "opened_trades": 0,
        "execution_rejections": [],
    }
    try:
        snap = engine._market_snapshot()
        result["market_snapshot"] = "PASS" if snap.get("ad_complete") and snap.get("sector", {}).get("available") else "BLOCKED"
        result["market_gate"] = "BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else "NO_ALIGNMENT"
        result["stocks_scanned"] = len(engine.references)
        signals = engine.scan()
        result["signals_generated"] = len(engine.last_signals) + sum(engine.diagnostics.get("signals_by_strategy", {}).values()) - len(engine.last_signals)
        result["signals_selected"] = len(signals)
        for sig in signals:
            s = str(sig.get("strategy", "")).upper()
            if s in result["strategy_candidates"]:
                result["strategy_candidates"][s] += 1
        for sig in signals:
            result["execution_attempts"] += 1
            opened = engine.paper_engine.open_trade({**sig, "approved": True, "strategy": sig.get("strategy")})
            if opened.get("opened"):
                result["opened_trades"] += 1
            else:
                result["execution_rejections"].append({"strategy": sig.get("strategy"), "symbol": sig.get("symbol"), "side": sig.get("side"), "reason": opened.get("reason")})
        result["worker"] = "PASS"
    except Exception as exc:
        result["worker"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return write(**result)
