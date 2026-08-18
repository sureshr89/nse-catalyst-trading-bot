from pathlib import Path
import sys
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from dashboard.strategy2_data import status, diagnostics, gaps, signals, format_price, format_pct

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Scanner", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=10000, key="s2_scanner_live")
ensure_bot_running()
render_nav()

st.title("🔎 Strategy 2 — Stock Scanner")
st.caption("NIFTY 500 • BUY + SELL gap-extension candidates • actual risk must be ₹1,400–₹1,500")
s = status() or {}
d = diagnostics() or {}
MIN_RISK, MAX_RISK = 1400.0, 1500.0

gap = gaps()
if gap.empty:
    message = s.get("message") or s.get("last_error") or "Opening-gap data is not available yet."
    st.warning(str(message))
else:
    board = gap.copy()
    if "OpeningSetup" in board.columns:
        board = board[board["OpeningSetup"].astype(str).isin(["OPEN_ABOVE_PDH", "OPEN_BELOW_PDL"])].copy()
    if "GapPercentFromPreviousClose" in board.columns:
        board["GapPercentFromPreviousClose"] = pd.to_numeric(board["GapPercentFromPreviousClose"], errors="coerce")
        board["GapMagnitude"] = board["GapPercentFromPreviousClose"].abs()
        board = board.sort_values("GapMagnitude", ascending=False)
    with st.expander("🏆 Opening GAP Priority — Both Directions", expanded=False):
        cols = [c for c in ["Symbol", "TodayOpen", "PDH", "PDL", "PreviousDayClose", "Gap", "GapPercentFromPreviousClose", "GapType", "OpeningSetup"] if c in board.columns]
        view = board[cols].head(150).copy()
        for c in ["TodayOpen", "PDH", "PDL", "PreviousDayClose", "Gap"]:
            if c in view.columns:
                view[c] = view[c].map(format_price)
        if "GapPercentFromPreviousClose" in view.columns:
            view["GapPercentFromPreviousClose"] = view["GapPercentFromPreviousClose"].map(format_pct)
        st.dataframe(view, use_container_width=True, hide_index=True, height=450)

st.subheader("🔴 Strategy 2 Reversal Decisions")
sig = signals()
if not sig.empty:
    if "setup_type" in sig.columns:
        sig = sig[sig["setup_type"].astype(str).str.contains("GAP_(UP|DOWN)_EXTENSION_REVERSAL", na=False)].copy()
    for col in ["entry", "stop_loss", "target", "risk_reward", "actual_risk", "risk_per_share", "position_value", "quantity", "estimated_risk", "estimated_quantity", "gap_percent"]:
        if col not in sig.columns:
            sig[col] = pd.NA
        sig[col] = pd.to_numeric(sig[col], errors="coerce")
    approved = sig.get("approved", pd.Series(False, index=sig.index)).astype(str).str.lower().isin({"true", "1", "yes"})
    sig["Approved"] = approved
    sig["Risk Band"] = sig["actual_risk"].map(
        lambda x: "₹1,400–₹1,500 — ELIGIBLE" if pd.notna(x) and MIN_RISK <= float(x) <= MAX_RISK
        else "Below ₹1,400 — REJECT" if pd.notna(x) and float(x) < MIN_RISK
        else "Above ₹1,500 — REJECT" if pd.notna(x) and float(x) > MAX_RISK
        else "Not calculated"
    )
    with st.expander("📋 Decision Details — risk, quantity, RR and rejection reason", expanded=False):
        st.info("Actual risk = |Entry − Stop Loss| × Quantity. Only ₹1,400–₹1,500 actual risk is eligible for a new S2 position.")
        cols = [c for c in ["timestamp", "symbol", "signal", "gap_percent", "entry", "stop_loss", "target", "quantity", "risk_per_share", "actual_risk", "risk_reward", "position_value", "original_stop_loss", "risk_adjusted", "priority_rank", "Approved", "Risk Band", "reason"] if c in sig.columns]
        st.dataframe(sig[cols].tail(200).iloc[::-1], use_container_width=True, hide_index=True, height=470)
else:
    st.info("No Strategy 2 reversal decisions recorded yet.")

with st.expander("📡 Scanner Diagnostics", expanded=False):
    st.dataframe(pd.DataFrame([
        ("Bot status", s.get("status", "STARTING")),
        ("Last scan", s.get("last_scan") or "Not scanned yet"),
        ("Opening candidates", d.get("candidates", 0)),
        ("BUY candidates", d.get("buy_candidates", 0)),
        ("SELL candidates", d.get("sell_candidates", 0)),
        ("BUY qualified", d.get("buy_qualified", 0)),
        ("SELL qualified", d.get("sell_qualified", 0)),
        ("Approved / taken", d.get("signals", 0)),
        ("Risk-adjusted", d.get("risk_adjusted", 0)),
    ], columns=["Metric", "Value"]), use_container_width=True, hide_index=True)

rejections = d.get("rejections", {}) or {}
if rejections:
    with st.expander("🚫 Rejection Audit — Why stocks were not selected", expanded=False):
        st.dataframe(pd.DataFrame([{"Reason": k, "Count": v} for k, v in sorted(rejections.items(), key=lambda x: x[1], reverse=True)]), use_container_width=True, hide_index=True)

render_daily_footer()
