from pathlib import Path
import json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from worker_service import ensure_worker_process

st.set_page_config(page_title="NSE Catalyst | NIFTY 500 Bot", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=5000, key="live")
st.markdown(load_css(), unsafe_allow_html=True)


def load(p, kind="json"):
    try:
        return json.loads(p.read_text()) if kind == "json" else pd.read_csv(p)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def grid(items):
    st.markdown(
        '<div class="metric-grid">' + ''.join(
            f'<div class="metric-card"><small>{a}</small><b>{b}</b></div>' for a, b in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


st.markdown("""<style>
.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:9px;min-height:52px}
.metric-card small{display:block;color:#9fb0c7;font-size:.62rem;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.metric-card b{display:block;color:#f4f7fb;font-size:.84rem;margin-top:3px;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
</style>""", unsafe_allow_html=True)

render_nav()

status = load(ROOT / "outputs/bot_status.json")
state = load(ROOT / "outputs/paper_engine_state.json")
try:
    live = ensure_worker_process()
    if isinstance(live, dict):
        status.update(live)
except Exception as error:
    status.setdefault("error", "Worker launcher: " + type(error).__name__ + ": " + str(error))


def heartbeat_alive(value, max_age_seconds=90):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max_age_seconds
    except Exception:
        return False


worker = bool(status.get("worker_alive", False)) and heartbeat_alive(status.get("heartbeat"))
bot = str(status.get("status", "STARTING")).upper()
if worker:
    st.success("🟢 NIFTY 500 BOT RUNNING • PAPER TRADING")
else:
    st.warning("🟠 NIFTY 500 WORKER NOT CONFIRMED ALIVE")

st.title("📈 NIFTY 500 Trading Bot")
st.caption("PDH/PDL reaction → today's Open 1-minute reversal • Paper trading only")
st.subheader("LIVE STATUS")
grid([
    ("India Time", datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")),
    ("Bot", bot), ("Worker", "ALIVE" if worker else "OFFLINE"),
    ("Scanner", status.get("scanner_status", "IDLE")),
    ("Open Positions", len(state.get("open_positions", {}) or {})),
    ("Heartbeat", status.get("heartbeat") or "—"),
])

st.subheader("CAPITAL & RISK")
grid([
    ("Starting Capital", "₹250,000"),
    ("Available", f"₹{float(status.get('available_capital', 250000) or 0):,.0f}"),
    ("Used", f"₹{float(status.get('used_capital', 0) or 0):,.0f}"),
    ("Risk / Trade", "₹1,400–₹1,500"), ("R:R", "1:1.25"), ("Max Positions", 2),
])

st.subheader("SCANNER ACTIVITY")
grid([
    ("NIFTY 500 Scans", status.get("scan_count", 0)),
    ("Cycle Count", status.get("cycle_count", 0)),
    ("Last Scan", status.get("last_scan") or "—"),
    ("Scan Duration", f'{float(status.get("scan_duration_seconds", 0) or 0):.2f}s'),
    ("Last Completed", status.get("last_scan_completed") or "—"),
    ("Last Signal Count", status.get("last_signal_count", 0)),
])

if status.get("error"):
    st.error(str(status.get("error")))
