"""Transparent live trade-path diagnostics for the paper-trading dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import streamlit as st

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PATH = OUT / "trade_path_diagnostics.json"


def capture(engine, cycle_result=None, error=None):
    """Record the NORMAL engine cycle without executing a second trade."""
    d = getattr(engine, "diagnostics", {}) or {}
    signals = getattr(engine, "last_signals", []) or []
    open_positions = getattr(getattr(engine, "paper_engine", None), "open_positions", {}) or {}
    rejection = d.get("rejections", {}) or {}
    coverage = str(d.get("market_data_coverage", "0/500"))
    ad_coverage = str(d.get("ad_coverage", "0/500"))
    sector_coverage = str(d.get("sector_priced", "0/500"))
    # The engine's market_data_source is informational only.  Do NOT classify
    # a valid Dhan 500/500 snapshot as BLOCKED merely because the source label
    # is DHAN_OHLC_LTP instead of an old DHAN_VERIFIED_500 string.
    market_snapshot = d.get("market_snapshot")
    if market_snapshot in {"PASS", "BLOCKED"}:
        market_status = market_snapshot
    else:
        market_status = "PASS" if coverage == "500/500" and ad_coverage == "500/500" and sector_coverage == "500/500" else "BLOCKED"
    gate = d.get("market_gate")
    if gate not in {"BUY", "SELL", "NO_ALIGNMENT"}:
        gate = "BUY" if d.get("buy_alignment") else "SELL" if d.get("sell_alignment") else "NO_ALIGNMENT"
    payload = {
        "timestamp": datetime.now(IST).isoformat(timespec="seconds"),
        "worker": "ERROR" if error else "PASS",
        "market_snapshot": market_status,
        "market_gate": gate,
        "strategy_market_gate": d.get("strategy_market_gate", "BLOCKED"),
        "stocks_scanned": d.get("stocks_scanned", 0),
        "strategy_reference_coverage": d.get("strategy_reference_coverage", "0/500"),
        "stock_coverage": coverage,
        "ad_coverage": ad_coverage,
        "sector_coverage": sector_coverage,
        "ad_ratio": d.get("ad_ratio"),
        "advances": d.get("ad_advances", 0),
        "declines": d.get("ad_declines", 0),
        "nifty500_change_pct": d.get("nifty500_change_pct"),
        "sector_change_pct": d.get("sector_change_pct"),
        "strategy_candidates": d.get("signals_by_strategy", {s: 0 for s in ["S1", "S2", "S3", "S4", "S5"]}),
        "signals_generated": len(signals),
        "signals_selected": int(d.get("final_signals", len(signals)) or 0),
        "execution_attempts": len(signals),
        "opened_trades": len(open_positions),
        "execution_rejections": rejection,
        "open_positions": list(open_positions.keys()) if isinstance(open_positions, dict) else [],
        "cycle_result_count": len(cycle_result or []),
        "error": f"{type(error).__name__}: {error}" if error else None,
    }
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return payload


def read():
    try:
        return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else None
    except Exception:
        return None


def render():
    data = read()
    if not data:
        st.info("Waiting for the first paper-trading engine cycle…")
        return
    st.markdown("### 🔎 Trade Path — Live Diagnostic")
    st.write(
        f"**Worker:** {data.get('worker')}  •  **Market:** {data.get('market_snapshot')}  •  "
        f"**Gate:** {data.get('market_gate')}  •  **Cycle:** {data.get('timestamp')}"
    )
    st.write(
        f"**Stocks:** {data.get('stock_coverage')}  •  **A/D:** {data.get('ad_coverage')} "
        f"({data.get('ad_ratio')})  •  **Sectors:** {data.get('sector_coverage')}  •  "
        f"**NIFTY:** {data.get('nifty500_change_pct')}%"
    )
    st.write(f"**Strategy references:** {data.get('strategy_reference_coverage', '0/500')}  •  **Strategy gate:** {data.get('strategy_market_gate', 'BLOCKED')}")
    cols = st.columns(5)
    candidates = data.get("strategy_candidates") or {}
    for col, strategy in zip(cols, ["S1", "S2", "S3", "S4", "S5"]):
        col.metric(strategy, candidates.get(strategy, 0))
    st.write(
        f"**Signals generated:** {data.get('signals_generated', 0)}  •  "
        f"**Execution attempts:** {data.get('execution_attempts', 0)}  •  "
        f"**Open trades:** {data.get('opened_trades', 0)}"
    )
    rejections = data.get("execution_rejections") or {}
    if rejections:
        st.warning("Execution/market rejection details: " + json.dumps(rejections, default=str))
    elif data.get("signals_generated", 0) == 0:
        st.info("No S1–S5 signal reached execution on the last cycle. The market/strategy gate is the stopping point.")
    else:
        st.success("Signal reached the execution path.")
    if data.get("error"):
        st.error(data["error"])
