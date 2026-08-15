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

# Apply the same shared typography/components used by every other dashboard page.
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="live")

# Start/keep exactly one persistent paper worker per Streamlit process.
try:
    ensure_bot_running()
except Exception as exc:
    st.error(f"Paper bot startup error: {type(exc).__name__}: {exc}")

status = get_status()

st.title("📈 NSE Catalyst Trading Bot")
st.caption("NIFTY 500 • PDH/PDL + Today's Open Reversal • Paper Trading")

render_nav()

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

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Bot Status", status_value)
with c2:
    st.metric("Open Positions", int(status.get("open_positions", 0) or 0))
with c3:
    st.metric("Available Capital", f"₹{float(status.get('available_capital', 0) or 0):,.0f}")
with c4:
    st.metric("Daily P&L", f"₹{float(status.get('daily_pnl', 0) or 0):,.0f}")

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
