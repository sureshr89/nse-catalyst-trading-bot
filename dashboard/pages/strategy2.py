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
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import diagnostics, state, format_price

st.set_page_config(page_title="NSE Catalyst | Strategy 2", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="strategy2_home_live")
ensure_strategy2_running()
render_nav()

st.title("🔴 Strategy 2 — Gap-Up Extension Reversal SELL")
st.caption("Dedicated Strategy 2 command center • ₹2,50,000 paper capital • NIFTY 500 • no ATR")
status = get_strategy2_status() or {}
d = diagnostics()
stt = state()

cards = st.columns(5)
cards[0].metric("Worker", status.get("status", "STARTING"))
cards[1].metric("Available Capital", format_price(status.get("available_capital", 250000)))
cards[2].metric("Open Positions", int(status.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", format_price(status.get("daily_pnl", 0)))
cards[4].metric("Last Scan", status.get("last_scan") or "—")
if status.get("message"):
    st.info(str(status["message"]))

st.subheader("⚡ Exact Strategy 2 Rules")
st.dataframe(pd.DataFrame([
    ("1. Opening setup", "Today's Open > PDH"),
    ("2. Extension", "After 09:45, price trades above Today's Open"),
    ("3. Trigger", "First completed 1-minute CLOSE below Today's Open"),
    ("4. Entry", "SELL at the completed trigger-candle close"),
    ("5. Stop", "Today's High at the trigger"),
    ("6. Target", "PDH"),
    ("7. Priority", "Largest opening GAP % from Previous Day Close first"),
    ("8. Market/news", "NIFTY and news are protective confirmation filters; Strategy 2 remains independent"),
    ("9. Risk", "₹1,400–₹1,500 intended risk • minimum 1.25R"),
], columns=["Step", "Rule"]), use_container_width=True, hide_index=True)

# The Strategy 2 page uses the same 3+3 navigation pattern as Strategy 1.
st.subheader("🔴 Strategy 2 Pages")
st.caption("Same professional layout as Strategy 1 — but every page reads Strategy 2 data only.")

rows = [
    [("📌 CURRENT TRADING", "pages/strategy2_current.py"),
     ("📊 COMPLETE ANALYSIS", "pages/strategy2_analysis.py"),
     ("🔎 STOCK SCANNER", "pages/strategy2_scanner.py")],
    [("📰 NEWS ANALYSIS", "pages/strategy2_news.py"),
     ("⬇️ DOWNLOADS", "pages/strategy2_downloads.py"),
     ("🔴 STRATEGY 2 HOME", "pages/strategy2.py")],
]
for row_index, row in enumerate(rows):
    cols = st.columns(3, gap="small")
    for col, (label, page) in zip(cols, row):
        with col:
            if st.button(label, key=f"strategy2_page_{row_index}_{label}", width="stretch"):
                st.switch_page(page)

st.divider()
st.subheader("📡 Live Diagnostics")
left, right = st.columns(2, gap="large")
with left:
    st.markdown("<div class='dashboard-info-card'>"
                f"<div class='session-row'><span>Last scan</span><b>{status.get('last_scan') or 'Not scanned yet'}</b></div>"
                f"<div class='session-row'><span>Signals</span><b>{int(status.get('last_signal_count', 0) or 0)}</b></div>"
                f"<div class='session-row'><span>Candidates</span><b>{int(d.get('candidates', 0) or 0)}</b></div>"
                f"<div class='session-row'><span>Qualified</span><b>{int(d.get('qualified', 0) or 0)}</b></div>"
                f"<div class='session-row'><span>Approved</span><b>{int(d.get('signals', 0) or 0)}</b></div>"
                "</div>", unsafe_allow_html=True)
with right:
    rejection_rows = [{"Reason": k, "Count": v} for k, v in (d.get("rejections", {}) or {}).items()]
    if rejection_rows:
        st.dataframe(pd.DataFrame(rejection_rows).sort_values("Count", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No Strategy 2 rejections recorded in the latest scan.")

st.subheader("🔒 Strategy Separation")
st.dataframe(pd.DataFrame([
    ("Capital", "Strategy 2 ₹2,50,000", "Strategy 1 capital never used", "SEPARATE"),
    ("Positions", "Strategy 2 positions only", "Strategy 1 positions never used", "SEPARATE"),
    ("Signals", "strategy2_signals.csv", "Strategy 1 signals.csv", "SEPARATE"),
    ("Trades", "strategy2_trades.csv", "Strategy 1 trades.csv", "SEPARATE"),
    ("Logic", "Gap-Up Extension Reversal SELL", "PDH/PDL Return", "DIFFERENT"),
], columns=["Data", "Strategy 2", "Strategy 1", "Status"]), use_container_width=True, hide_index=True)

st.caption("Paper trading only. Strategy 2 cannot use Strategy 1's capital, positions, journal, trade counts or risk state.")
render_daily_footer()
