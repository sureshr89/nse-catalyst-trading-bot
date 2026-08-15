from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Make repository imports reliable on Streamlit Cloud and locally.
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

st.set_page_config(page_title="NSE Catalyst | NIFTY 500 Bot", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="live")

try:
    ensure_bot_running()
except Exception as exc:
    st.error(f"Paper bot startup error: {type(exc).__name__}: {exc}")

status = get_status()
render_nav()
st.title("📈 NSE Catalyst Trading Bot")
st.caption("NIFTY 500 • PDH/PDL + Today's Open Reversal • Paper Trading")

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

# Same responsive 2×2 metric-card component as Current Trading.
def cards(items):
    html = "<div class='metric-grid'>" + "".join(
        f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
        for label, value in items
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

# Weekend/idle status files may legitimately omit paper-engine capital fields.
# In that case show the configured paper capital rather than displaying ₹0.
# If the status explicitly contains a value (including 0 after trading), preserve it.
available_capital = status.get("available_capital")
if available_capital is None:
    available_capital = getattr(settings, "TOTAL_CAPITAL", 0)

daily_pnl = status.get("daily_pnl", 0)

cards([
    ("Bot Status", status_value),
    ("Open Positions", int(status.get("open_positions", 0) or 0)),
    ("Available Capital", f"₹{float(available_capital or 0):,.0f}"),
    ("Daily P&L", f"₹{float(daily_pnl or 0):,.0f}"),
])

st.divider()

# Strategy and Session are presented as equal dashboard cards so the desktop
# layout is balanced and the mobile layout stacks cleanly.
left, right = st.columns(2, gap="large")
with left:
    st.subheader("Strategy")
    st.markdown("<div class='dashboard-info-card'>"
                "<div class='info-row'><span>BUY</span><b>Open above PDH → price below PDH → Open reversal → NIFTY 500 ≥ +0.25%</b></div>"
                "<div class='info-row'><span>SELL</span><b>Open below PDL → price above PDL → Open reversal → NIFTY 500 ≤ −0.25%</b></div>"
                "<div class='info-row'><span>RISK</span><b>SL: PDH / PDL &nbsp;•&nbsp; Target: 1.25R &nbsp;•&nbsp; Max positions: 2</b></div>"
                "</div>", unsafe_allow_html=True)
with right:
    st.subheader("Session")
    now = datetime.now(INDIA_TZ).strftime("%d-%b-%Y %H:%M:%S IST")
    st.markdown("<div class='dashboard-info-card'>"
                f"<div class='session-row'><span>Current time</span><b>{now}</b></div>"
                f"<div class='session-row'><span>Last scan</span><b>{status.get('last_scan_completed') or 'Not scanned yet'}</b></div>"
                f"<div class='session-row'><span>Signals in last scan</span><b>{int(status.get('last_signal_count', 0) or 0)}</b></div>"
                "</div>", unsafe_allow_html=True)
    if status.get("last_scan_error"):
        st.warning(str(status.get("last_scan_error")))

st.caption("Paper trading only. Live order execution is disabled.")
render_daily_footer()
