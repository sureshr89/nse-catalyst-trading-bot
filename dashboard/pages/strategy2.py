from pathlib import Path
import sys
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import diagnostics, state, format_price, format_pct

st.set_page_config(page_title="NSE Catalyst | Strategy 2", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="strategy2_home_live")
ensure_strategy2_running()
render_nav()

st.title("🔴 Strategy 2 — Gap-Up Extension Reversal SELL")
st.caption("Complete separate dashboard • ₹2,50,000 paper capital • NIFTY 500 • no ATR")
status = get_strategy2_status() or {}
d = diagnostics()
stt = state()

cards = st.columns(5)
cards[0].metric("Worker", status.get("status", "STARTING"))
cards[1].metric("Available Capital", format_price(status.get("available_capital", 250000)))
cards[2].metric("Open Positions", int(status.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", format_price(status.get("daily_pnl", 0)))
cards[4].metric("Last Scan", status.get("last_scan") or "—")
if status.get("message"): st.info(str(status["message"]))

st.subheader("⚡ Exact Strategy")
st.dataframe(__import__("pandas").DataFrame([
    ("1. Opening setup", "Today's Open > PDH"),
    ("2. Extension", "After 09:45, price trades above Today's Open"),
    ("3. Trigger", "First completed 1-minute CLOSE below Today's Open"),
    ("4. Entry", "SELL at the completed candle close"),
    ("5. Stop", "Today's High at the trigger"),
    ("6. Target", "PDH"),
    ("7. Priority", "Largest opening GAP % from Previous Day Close first"),
    ("8. NIFTY filter", "Only clearly bullish NIFTY 500 (> +0.25%) blocks the short"),
    ("9. Risk", "₹1,400–₹1,500 intended risk • minimum 1.25R"),
], columns=["Step", "Rule"]), use_container_width=True, hide_index=True)

st.subheader("📚 Strategy 2 Pages")
links = [
    ("📌 Current Trading", "pages/strategy2_current.py", "Live worker, positions, signals and rejection audit"),
    ("📊 Complete Analysis", "pages/strategy2_analysis.py", "P&L, setup, stock, GAP, risk and timing analysis"),
    ("🔎 Stock Scanner", "pages/strategy2_scanner.py", "Opening GAP priority and reversal candidates"),
    ("📰 News Analysis", "pages/strategy2_news.py", "Every news decision and approval/rejection"),
    ("⬇️ Downloads", "pages/strategy2_downloads.py", "Trades, signals, diagnostics and paper state"),
]
for label, page, description in links:
    c1, c2 = st.columns([1, 3])
    with c1: st.page_link(page, label=label, use_container_width=True)
    with c2: st.caption(description)

st.subheader("📡 Live Diagnostics")
st.write({
    "last_scan": status.get("last_scan"),
    "signals_in_last_scan": status.get("last_signal_count", 0),
    "opening_candidates": d.get("candidates", 0),
    "qualified_reversals": d.get("qualified", 0),
    "approved_signals": d.get("signals", 0),
    "rejections": d.get("rejections", {}),
    "open_positions": len(stt.get("open_positions", {}) or {}),
})

st.caption("Paper trading only. Strategy 2 cannot use Strategy 1's capital, positions, journal, trade counts or risk state.")
render_daily_footer()
