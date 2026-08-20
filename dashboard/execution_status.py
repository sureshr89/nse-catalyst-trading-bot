"""Compact live execution-path status panel."""
from pathlib import Path
import json
import streamlit as st

PATH = Path("outputs/trade_path_diagnostics.json")

def render_execution_status():
    st.markdown("### 🔎 Trade Path — Live Diagnostic")
    if not PATH.exists():
        st.info("Waiting for the first paper-trading engine cycle…")
        return
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        st.error(f"Diagnostic read error: {type(exc).__name__}: {exc}")
        return
    rows = [
        ("Worker", data.get("worker_status", "WAITING")),
        ("Market snapshot", data.get("market_snapshot", "WAITING")),
        ("Market gate", data.get("market_gate", "WAITING")),
        ("Stocks scanned", data.get("stocks_scanned", 0)),
        ("Signals selected", data.get("final_signals", data.get("signals_selected", 0))),
        ("Execution attempts", data.get("execution_attempts", 0)),
        ("Paper trades opened", data.get("execution_opened", 0)),
        ("Execution rejected", data.get("execution_rejected", 0)),
        ("Last cycle", data.get("timestamp", "—")),
    ]
    st.dataframe({"Check": [r[0] for r in rows], "Value": [r[1] for r in rows]}, hide_index=True, width="stretch")
    rejected = data.get("execution_rejections") or []
    if rejected:
        st.warning("Execution rejection details")
        st.dataframe(rejected, hide_index=True, width="stretch")
    if data.get("error"):
        st.error(str(data["error"]))
