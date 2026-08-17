from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from config import settings
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running, get_status
from strategy2_worker import ensure_strategy2_running, get_strategy2_status

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst | Dashboard",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="live")

# Start both paper workers independently. A worker failure must not prevent the
# dashboard itself from rendering; the worker status is shown below.
startup_error = None
try:
    ensure_bot_running()
    ensure_strategy2_running()
except Exception as exc:
    startup_error = f"{type(exc).__name__}: {exc}"

status = get_status() or {}
strategy2 = get_strategy2_status() or {}
render_nav()

st.title("📈 NSE Catalyst — Dashboard")
st.caption("Two completely separate paper strategies • separate logic • separate capital • separate positions • separate journals")

if startup_error:
    st.error(f"Paper worker startup error: {startup_error}")


def cards(items):
    html = "<div class='metric-grid'>" + "".join(
        f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
        for label, value in items
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

available_capital = status.get("available_capital")
if available_capital is None:
    available_capital = getattr(settings, "TOTAL_CAPITAL", 250000)
s1_capital = float(available_capital or 0)
s2_capital = float(strategy2.get("available_capital", 250000) or 0)

cards([
    ("🔵 STRATEGY 1 STATUS", str(status.get("status", "UNKNOWN"))),
    ("🔵 S1 AVAILABLE", f"₹{s1_capital:,.0f}"),
    ("🔴 STRATEGY 2 STATUS", str(strategy2.get("status", "STARTING"))),
    ("🔴 S2 AVAILABLE", f"₹{s2_capital:,.0f}"),
])

st.divider()

st.markdown("### 🔵 STRATEGY 1 — PDH/PDL RETURN")
st.caption("This section belongs ONLY to Strategy 1. Its data comes from Strategy 1's scanner, paper engine, signals and journal.")
left, right = st.columns(2, gap="large")
with left:
    st.markdown(
        "<div class='dashboard-info-card'><div class='info-row'><span>SETUP</span><b>Gap above PDH for BUY / gap below PDL for SELL</b></div><div class='info-row'><span>TRIGGER</span><b>Required PDH/PDL breach → return to Today's Open using completed 1-minute CLOSE</b></div><div class='info-row'><span>ENTRY</span><b>Final Strategy 1 confirmation → current market price</b></div><div class='info-row'><span>RISK</span><b>SL at PDH/PDL • Target 1.25R • separate ₹2,50,000 paper account</b></div></div>",
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        "<div class='dashboard-info-card'><div class='session-row'><span>Status</span><b>" + str(status.get("status", "UNKNOWN")) + "</b></div><div class='session-row'><span>Last scan</span><b>" + str(status.get("last_scan_completed") or "Not scanned yet") + "</b></div><div class='session-row'><span>Signals</span><b>" + str(int(status.get("last_signal_count", 0) or 0)) + "</b></div><div class='session-row'><span>Capital</span><b>₹" + f"{s1_capital:,.0f}" + "</b></div></div>",
        unsafe_allow_html=True,
    )
if status.get("last_scan_error"):
    st.warning(f"Strategy 1: {status.get('last_scan_error')}")
if status.get("message"):
    st.info(f"Strategy 1 — {status.get('message')}")

st.markdown("### 🔴 STRATEGY 2 — GAP EXTENSION REVERSAL BUY + SELL")
st.caption("Strategy 2 is independent and supports both gap-up reversal SELL and gap-down reversal BUY setups.")
left, right = st.columns(2, gap="large")
with left:
    st.markdown(
        "<div class='dashboard-info-card'><div class='info-row'><span>SELL SETUP</span><b>Today's Open &gt; PDH → extension above Open → after 09:45 first completed 1-minute CLOSE below Open</b></div><div class='info-row'><span>BUY SETUP</span><b>Today's Open &lt; PDL → extension below Open → after 09:45 first completed 1-minute CLOSE above Open</b></div><div class='info-row'><span>ENTRY</span><b>Enter at the completed trigger candle close</b></div><div class='info-row'><span>RISK</span><b>SELL: SL Today's High / Target PDH • BUY: SL Today's Low / Target PDL • separate ₹2,50,000 account</b></div></div>",
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        "<div class='dashboard-info-card'><div class='session-row'><span>Status</span><b>" + str(strategy2.get("status", "STARTING")) + "</b></div><div class='session-row'><span>Last scan</span><b>" + str(strategy2.get("last_scan") or "Not scanned yet") + "</b></div><div class='session-row'><span>Signals</span><b>" + str(int(strategy2.get("last_signal_count", 0) or 0)) + "</b></div><div class='session-row'><span>Capital</span><b>₹" + f"{s2_capital:,.0f}" + "</b></div></div>",
        unsafe_allow_html=True,
    )
if strategy2.get("last_error"):
    st.warning(f"Strategy 2: {strategy2.get('last_error')}")
if strategy2.get("message"):
    st.info(f"Strategy 2 — {strategy2.get('message')}")

st.divider()
st.subheader("🔒 Separation Check")
st.dataframe(
    __import__("pandas").DataFrame([
        ("Capital", "Strategy 1 account", "Strategy 2 account", "SEPARATE"),
        ("Positions", "Strategy 1 paper positions", "Strategy 2 paper positions", "SEPARATE"),
        ("Signals", "outputs/signals.csv", "outputs/strategy2_signals.csv", "SEPARATE"),
        ("Trades", "outputs/trades.csv", "outputs/strategy2_trades.csv", "SEPARATE"),
        ("State", "paper_engine_state.json", "strategy2_paper_engine_state.json", "SEPARATE"),
        ("Strategy logic", "PDH/PDL return", "Gap extension reversal BUY + SELL", "DIFFERENT"),
    ], columns=["Data", "Strategy 1", "Strategy 2", "Status"]),
    width="stretch",
    hide_index=True,
)

st.caption("Paper trading only. Strategy 1 and Strategy 2 are independent systems; neither strategy can use the other strategy's capital, positions, journal or risk state.")
render_daily_footer()
