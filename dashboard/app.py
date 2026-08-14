from pathlib import Path
import json,sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from dashboard.nav import render_nav
from bot_runner import ensure_bot_running
st.set_page_config(page_title="NSE Catalyst | Bot Status",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=5000,key="live")
def load(p,kind="json"):
    try:return json.loads(p.read_text()) if kind=="json" else pd.read_csv(p)
    except Exception:return {} if kind=="json" else pd.DataFrame()
def grid(x):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><small>{a}</small><b>{b}</b></div>' for a,b in x)+'</div>',unsafe_allow_html=True)
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
.block-container{padding:.4rem!important}
.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px;min-height:50px}
.metric-card small{display:block;color:#9fb0c7;font-size:.58rem}.metric-card b{display:block;color:#f4f7fb;font-size:.82rem;margin-top:3px}
[data-testid="stPlotlyChart"],[data-testid="stPlotlyChart"] *{pointer-events:none!important;touch-action:none!important}
</style>""",unsafe_allow_html=True)
render_nav()
status=load(ROOT/"outputs/bot_status.json");state=load(ROOT/"outputs/paper_engine_state.json")
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error:
    status["error"]=f"Worker startup/status error: {type(error).__name__}: {error}"
worker=bool(status.get("worker_alive",False)); bot=str(status.get("status","STARTING")).upper()
if worker and bot=="WAITING":st.warning("🟡 BOT READY • WAITING FOR MARKET SESSION")
elif worker:st.success("🟢 BOT RUNNING • PAPER TRADING")
else:st.warning("🟠 WORKER NOT CONFIRMED ALIVE")
st.subheader("LIVE STATUS");grid([("India Time",datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")),("Bot",bot),("Worker","ALIVE" if worker else "OFFLINE"),("Scanner",status.get("scanner_status","IDLE")),("Open Positions",len(state.get("open_positions",{}) or {})),("Heartbeat",status.get("heartbeat") or "—")])
st.subheader("CAPITAL & RISK");grid([("Starting Capital","₹250,000"),("Available",f"₹{float(status.get('available_capital',250000) or 0):,.0f}"),("Used",f"₹{float(status.get('used_capital',0) or 0):,.0f}"),("Risk / Trade","₹1,400–₹1,500"),("R:R","1:1.25"),("Max Positions",2)])
st.caption("P&L, closed-trade performance and daily/monthly results are shown on the Analysis page so the same figures are not repeated here.")
st.subheader("SCANNER ACTIVITY");grid([("Total Scans",status.get("scan_count",0)),("Cycle Count",status.get("cycle_count",0)),("Last Scan",status.get("last_scan") or "—"),("Scan Duration",f'{float(status.get("scan_duration_seconds",0) or 0):.2f}s'),("Last Completed",status.get("last_scan_completed") or "—"),("Last Signal Count",status.get("last_signal_count",0))])
with st.expander("SYSTEM DIAGNOSTICS"):
    st.json({"Last bot cycle":status.get("last_cycle"),"Heartbeat":status.get("heartbeat"),"Worker":worker,"Status":status.get("message") or "—","Last Scan":status.get("last_scan"),"Scan Count":status.get("scan_count",0),"Last Signal Count":status.get("last_signal_count",0),"Last Completed":status.get("last_scan_completed") or "—","Error":status.get("error")})
