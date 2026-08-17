from pathlib import Path
import sys
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import diagnostics, gaps, signals, format_price, format_pct

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Scanner", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=10000, key="s2_scanner_live")
ensure_strategy2_running()
render_nav()

st.title("🔎 Strategy 2 — Stock Scanner")
st.caption("NIFTY 500 • OPEN_ABOVE_PDH candidates • largest opening GAP priority • reversal state")
s = get_strategy2_status() or {}
d = diagnostics()

gap = gaps()
if gap.empty:
    st.info("Opening-gap data is not available yet. The worker prepares it before the trading window.")
else:
    board = gap.copy()
    if "OpeningSetup" in board.columns:
        board = board[board["OpeningSetup"].astype(str).eq("OPEN_ABOVE_PDH")].copy()
    if "GapPercentFromPreviousClose" in board.columns:
        board["GapPercentFromPreviousClose"] = pd.to_numeric(board["GapPercentFromPreviousClose"], errors="coerce")
        board = board.sort_values("GapPercentFromPreviousClose", ascending=False)
    st.subheader("🏆 Opening GAP Priority")
    cols = [c for c in ["Symbol", "TodayOpen", "PDH", "PreviousDayClose", "Gap", "GapPercentFromPreviousClose", "OpeningSetup"] if c in board.columns]
    view = board[cols].head(100).copy()
    for c in ["TodayOpen", "PDH", "PreviousDayClose", "Gap"]:
        if c in view.columns: view[c] = view[c].map(format_price)
    if "GapPercentFromPreviousClose" in view.columns: view["GapPercentFromPreviousClose"] = view["GapPercentFromPreviousClose"].map(format_pct)
    st.dataframe(view, use_container_width=True, hide_index=True, height=420)

st.subheader("🔴 Strategy 2 Reversal Candidates")
sig = signals()
if not sig.empty:
    if "setup_type" in sig.columns:
        sig = sig[sig["setup_type"].astype(str).str.contains("GAP_UP_EXTENSION_REVERSAL", na=False)].copy()
    cols = [c for c in ["timestamp", "symbol", "gap_percent", "today_open", "pdh", "today_high", "trigger_close", "entry", "stop_loss", "target", "risk_reward", "priority_rank", "approved", "reason"] if c in sig.columns]
    if not sig.empty:
        st.dataframe(sig[cols].tail(150).iloc[::-1], use_container_width=True, hide_index=True, height=420)
    else:
        st.info("No Strategy 2 reversal decisions recorded yet.")
else:
    st.info("No Strategy 2 signal records yet.")

st.subheader("📡 Scanner Diagnostics")
st.write({
    "worker_status": s.get("status"),
    "last_scan": s.get("last_scan"),
    "opening_candidates": d.get("candidates", 0),
    "qualified_reversals": d.get("qualified", 0),
    "approved": d.get("signals", 0),
    "rejections": d.get("rejections", {}),
})
render_daily_footer()
