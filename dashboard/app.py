from pathlib import Path
import sys
from datetime import datetime
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

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst | NIFTY 500 Bot",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="live")

try:
    ensure_bot_running()
except Exception as exc:
    st.error(f"Paper bot startup error: {type(exc).__name__}: {exc}")

status = get_status()
render_nav()
st.title("📈 NSE Catalyst Trading Bot")
st.caption("NIFTY 500 • PDH/PDL + Today's Open Return • Paper Trading")

status_value = str(status.get("status", "UNKNOWN"))
message = str(status.get("message", "No status message available."))
if status_value == "ERROR":
    st.error(message)
elif status_value in {"RUNNING", "PREPARING"}:
    st.success(message)
elif status_value == "WAITING":
    st.info(message)
else:
    st.warning(message)


def cards(items):
    html = "<div class='metric-grid'>" + "".join(
        f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
        for label, value in items
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


available_capital = status.get("available_capital")
if available_capital is None:
    available_capital = getattr(settings, "TOTAL_CAPITAL", 0)

cards([
    ("Bot Status", status_value),
    ("Open Positions", int(status.get("open_positions", 0) or 0)),
    ("Available Capital", f"₹{float(available_capital or 0):,.0f}"),
    ("Daily P&L", f"₹{float(status.get('daily_pnl', 0) or 0):,.0f}"),
])

st.divider()
left, right = st.columns(2, gap="large")

with left:
    st.subheader("Strategy")
    st.markdown(
        "<div class='dashboard-info-card'>"
        "<div class='info-row'><span>BUY</span><b>Open above PDH → completed 1m close below PDH → completed 1m close back to Today's Open → NIFTY 500 ≥ +0.25%</b></div>"
        "<div class='info-row'><span>SELL</span><b>Open below PDL → completed 1m close above PDL → completed 1m close back to Today's Open → NIFTY 500 ≤ −0.25%</b></div>"
        "<div class='info-row'><span>PRIORITY</span><b>Largest qualifying absolute GAP % first → News gate → risk validation → available slot</b></div>"
        "<div class='info-row'><span>RISK</span><b>SL: PDH / PDL • Target: 1.25R • Risk: ₹1,400–₹1,500 • Max positions: 2</b></div>"
        "</div>",
        unsafe_allow_html=True,
    )

with right:
    st.subheader("Session")
    now = datetime.now(INDIA_TZ).strftime("%d-%b-%Y %H:%M:%S IST")
    st.markdown(
        "<div class='dashboard-info-card'>"
        f"<div class='session-row'><span>Current time</span><b>{now}</b></div>"
        f"<div class='session-row'><span>Last scan</span><b>{status.get('last_scan_completed') or 'Not scanned yet'}</b></div>"
        f"<div class='session-row'><span>Signals in last scan</span><b>{int(status.get('last_signal_count', 0) or 0)}</b></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if status.get("last_scan_error"):
        st.warning(str(status.get("last_scan_error")))

st.caption("Paper trading only. Live order execution is disabled.")
render_daily_footer()
