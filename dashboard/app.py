from pathlib import Path
import json,importlib.util,sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
st.set_page_config(page_title="NSE Catalyst | Bot Status",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=5000,key="live")
def load(p,kind="json"):
 try:return json.loads(p.read_text()) if kind=="json" else pd.read_csv(p)
 except Exception:return {} if kind=="json" else pd.DataFrame()
def grid(x):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><small>{a}</small><b>{b}</b></div>' for a,b in x)+'</div>',unsafe_allow_html=True)
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}.block-container{padding:.4rem!important}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px;min-height:50px}.metric-card small{display:block;color:#9fb0c7;font-size:.58rem}.metric-card b{display:block;color:#f4f7fb;font-size:.82rem;margin-top:3px}[data-testid="stPageLink"] a{min-height:38px!important;margin-bottom:7px!important;border:1px solid #2b3b57!important;border-radius:10px!important;background:#142036!important;color:#e9f0f8!important;justify-content:center!important;font-size:.60rem!important;font-weight:700!important}
</style>""",unsafe_allow_html=True)
with st.container(key="nav"):
 l,r=st.columns(2,gap="small")
 with l:st.page_link("app.py",label="🟢 BOT STATUS",width="stretch");st.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
 with r:st.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch");st.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")
status=load(ROOT/"outputs/bot_status.json");state=load(ROOT/"outputs/paper_engine_state.json");trades=load(ROOT/"outputs/trades.csv","csv");signals=load(ROOT/"outputs/signals.csv","csv")
try:
 spec=importlib.util.spec_from_file_location("runner",ROOT/"bot_runner.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.ensure_bot_running();live=mod.get_status();status.update(live if isinstance(live,dict) else {})
except Exception:pass
worker=bool(status.get("worker_alive",False));bot=str(status.get("status","STARTING")).upper()
st.warning("🟡 BOT READY • WAITING FOR MARKET SESSION" if worker and bot=="WAITING" else ("🟢 BOT RUNNING • PAPER TRADING" if worker else "🟠 WORKER NOT CONFIRMED ALIVE"))
st.subheader("LIVE STATUS");grid([("India Time",datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")),("Bot",bot),("Worker","ALIVE" if worker else "OFFLINE"),("Scanner",status.get("scanner_status","IDLE")),("Open Positions",len(state.get("open_positions",{}) or {})),("Daily P&L",f"₹{float(status.get('daily_pnl',0) or 0):,.0f}")])
st.subheader("CAPITAL & RISK");grid([("Starting Capital","₹250,000"),("Available",f"₹{float(status.get('available_capital',250000) or 0):,.0f}"),("Used",f"₹{float(status.get('used_capital',0) or 0):,.0f}"),("Risk / Trade","₹1,400–₹1,500"),("R:R","1:1.25"),("Max Positions",2)])
closed=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
wins=int((closed["pnl"]>0).sum()) if not closed.empty else 0;losses=int((closed["pnl"]<0).sum()) if not closed.empty else 0;pnl=float(closed["pnl"].sum()) if not closed.empty else 0
st.subheader("TODAY'S TRADING");grid([("Closed Trades",len(closed)),("Wins / Losses",f"{wins} / {losses}"),("Win Rate",f"{wins/len(closed)*100:.1f}%" if len(closed) else "0.0%"),("Realized P&L",f"₹{pnl:,.2f}")])
st.subheader("SCANNER ACTIVITY");grid([("Total Scans",status.get("scan_count",0)),("Unique Signals",len(signals)),("Cycle Count",status.get("cycle_count",0)),("Last Scan",status.get("last_scan") or "—"),("Scan Duration",f'{float(status.get("scan_duration_seconds",0) or 0):.2f}s'),("Last Completed",status.get("last_scan_completed") or "—")])
with st.expander("SYSTEM DIAGNOSTICS"):st.json({"Last bot cycle":status.get("last_cycle"),"Heartbeat":status.get("heartbeat"),"Worker":worker,"Status":status.get("message") or "—"})
