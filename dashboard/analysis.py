"""Read-only trading analysis page.

This page intentionally does not start the worker, place trades, mutate state,
or write any files. It only reads the persistent trade journal/state already
maintained by the trading bot.
"""
from pathlib import Path
import json

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"

st.set_page_config(
    page_title="NSE Catalyst - Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Trading Analysis")
st.caption("Read-only analysis page — no trading logic, worker, or state is changed here.")


def load_trades():
    if not TRADES_FILE.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(TRADES_FILE)
    except Exception:
        return pd.DataFrame()


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


trades = load_trades()
state = load_state()

if trades.empty:
    st.info("No persistent trade journal data is available yet.")
else:
    closed = trades.copy()
    if "status" in closed.columns:
        closed = closed[closed["status"].astype(str).str.upper() == "CLOSED"].copy()

    if "pnl" in closed.columns:
        closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)

    total = len(closed)
    wins = int((closed["pnl"] > 0).sum()) if total else 0
    losses = int((closed["pnl"] < 0).sum()) if total else 0
    pnl = float(closed["pnl"].sum()) if total else 0.0
    win_rate = (wins / total * 100.0) if total else 0.0
    open_count = len(state.get("open_positions", {}) or {})

    a, b, c, d, e = st.columns(5)
    a.metric("Closed Trades", total)
    b.metric("Winning Trades", wins)
    c.metric("Losing Trades", losses)
    d.metric("Win Rate", f"{win_rate:.1f}%")
    e.metric("Open Positions", open_count)

    st.metric("Realized P&L", f"₹{pnl:,.2f}")

    st.subheader("Trade Details")
    st.dataframe(closed, use_container_width=True, hide_index=True)

st.divider()
st.caption("Analysis is read-only. Trade execution and persistence remain on the main trading dashboard/worker.")
