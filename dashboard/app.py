from pathlib import Path
import json,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
st.set_page_config(page_title="NSE Catalyst | NIFTY 500 Bot",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=5000,key="live");st.markdown(load_css(),unsafe_allow_html=True)
def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}
def grid(items):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><small>{a}</small><b>{b}</b></div>' for a,b in items)+'</div>',unsafe_allow_html=True)
def heartbeat_alive(value,max_age_seconds=90):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"));stamp=stamp.replace(tzinfo=ZoneInfo("Asia/Kolkata")) if stamp.tzinfo is None else stamp;age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds();return 0<=age<=max_age_seconds
    except Exception:return False
render_nav();status=load(ROOT/"outputs/bot_status.json");state=load(ROOT/"outputs/paper_engine_state.json")
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error:status.setdefault("error",f"Worker launcher: {type(error).__name__}: {error}")
worker=bool(status.get("worker_alive",False)) and heartbeat_alive(status.get("heartbeat"));bot=str(status.get("status","STARTING")).upper()
st.title("📈 NIFTY 500 Trading Bot");st.caption("Direct 1-minute price strategy • PDH/PDL breach → return to Today's Open → entry • Paper trading only")
if worker:st.success("🟢 NIFTY 500 BOT RUNNING • PAPER TRADING")
else:st.warning("🟠 NIFTY 500 WORKER NOT CONFIRMED ALIVE")
st.subheader("LIVE BOT STATUS");grid([("India Time",datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")),("Bot",bot),("Worker","ALIVE" if worker else "OFFLINE"),("Scanner",status.get("scanner_status","IDLE")),("Open Positions",len(state.get("open_positions",{}) or {})),("Heartbeat",status.get("heartbeat") or "—")])
st.subheader("STRATEGY CONDITIONS");grid([("Universe","NIFTY 500"),("Data","Current completed 1-minute prices"),("BUY","Open > PDH → price below PDH → return to Open"),("SELL","Open < PDL → price above PDL → return to Open"),("NIFTY Filter","BUY ≥ +0.25% / SELL ≤ −0.25%"),("Entry Window","09:45–14:00 IST"),("BUY SL","PDH"),("SELL SL","PDL"),("Target","1.25 × entry-to-SL risk"),("Square-off","15:00 IST")])
st.subheader("CAPITAL & RISK");grid([("Starting Capital","₹250,000"),("Available",f"₹{float(status.get('available_capital',250000) or 0):,.0f}"),("Used",f"₹{float(status.get('used_capital',0) or 0):,.0f}"),("Risk / Trade","₹1,400–₹1,500"),("R:R","1:1.25"),("Max Positions",2)])
st.subheader("SCANNER ACTIVITY");grid([("NIFTY 500 Scans",status.get("scan_count",0)),("Cycle Count",status.get("cycle_count",0)),("Last Scan",status.get("last_scan") or "—"),("Scan Duration",f'{float(status.get("scan_duration_seconds",0) or 0):.2f}s'),("Last Completed",status.get("last_scan_completed") or "—")])
if status.get("error"):st.error(str(status.get("error")))
render_daily_footer()
