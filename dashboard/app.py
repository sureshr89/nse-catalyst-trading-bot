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

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running, get_status

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst | NIFTY 500 Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# One shared typography/style system for every dashboard page.
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="live")

# Start/keep exactly one persistent paper worker per Streamlit process.
try:
    ensure_bot_running()
except Exception as exc:
    st.error(f"Paper bot startup error: {type(exc).__name__}: {exc}")

status = get_status()

# Keep page structure identical to the other dashboard pages:
# navigation first, then the page title/content.
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

# Use the same responsive 2×2 metric-card component as Current Trading.
def cards(items):
    html = "<div class='metric-grid'>" + "".join(
        f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
        for label, value in items
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

cards([
    ("Bot Status", status_value),
    ("Open Positions", int(status.get("open_positions", 0) or 0)),
    ("Available Capital", f"₹{float(status.get('available_capital', 0) or 0):,.0f}"),
    ("Daily P&L", f"₹{float(status.get('daily_pnl', 0) or 0):,.0f}"),
])

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Strategy")
    st.write("**BUY:** Open above PDH → price below PDH → Open reversal → NIFTY 500 ≥ +0.25%")
    st.write("**SELL:** Open below PDL → price above PDL → Open reversal → NIFTY 500 ≤ −0.25%")
    st.write("**SL:** PDH / PDL  •  **Target:** 1.25R  •  **Max positions:** 2")
with right:
    st.subheader("Session")
    now = datetime.now(INDIA_TZ).strftime("%d-%b-%Y %H:%M:%S IST")
    st.write(f"Current time: **{now}**")
    st.write(f"Last scan: **{status.get('last_scan_completed') or 'Not scanned yet'}**")
    st.write(f"Signals in last scan: **{int(status.get('last_signal_count', 0) or 0)}**")
    if status.get("last_scan_error"):
        st.warning(str(status.get("last_scan_error")))

st.caption("Paper trading only. Live order execution is disabled.")
render_daily_footer()
