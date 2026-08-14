import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from dashboard.nav import render_nav
ROOT=Path(__file__).resolve().parents[2]
INDIA_TZ=ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px;min-height:52px}.metric-label{font-size:.58rem;color:#9fb0c7}.metric-value{font-size:.84rem;color:#f4f7fb;font-weight:750;margin-top:3px}
</style>
""",unsafe_allow_html=True)
render_nav()
def read(p,kind):
    try:return json.loads(p.read_text()) if kind=="json" else pd.read_csv(p)
    except Exception:return {} if kind=="json" else pd.DataFrame()
def grid(items):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><div class="metric-label">{a}</div><div class="metric-value">{b}</div></div>' for a,b in items)+'</div>',unsafe_allow_html=True)
def latest_rows(df,statuses):
    if df.empty or "status" not in df.columns:return pd.DataFrame()
    return df[df["status"].astype(str).str.upper().isin(statuses)].iloc[::-1].head(30).copy()
s=read(ROOT/"outputs/bot_status.json","json");state=read(ROOT/"outputs/paper_engine_state.json","json");pos=state.get("open_positions",{}) or {};trades=read(ROOT/"outputs/trades.csv","csv")
closed=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
st.title("📌 Current Trading")
st.caption("Only live positions, the latest closed trade and executed/capital-missed records are shown here. Overall performance is on Analysis.")
grid([("Bot",s.get("status","UNKNOWN")),("Worker","ALIVE" if s.get("worker_alive") else "OFFLINE"),("Open Positions",len(pos)),("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.0f}")])
st.subheader("Open Positions")
if pos:
    rows=[]
    for symbol,p in pos.items():rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("actual_risk",p.get("risk")),"R:R":p.get("rr",p.get("risk_reward",1.25)),"Entry Time":p.get("entry_time"),"Setup":p.get("setup_type","GAP_FAILURE_OPEN_RECLAIM"),"PDC":p.get("pdc"),"Today Open":p.get("today_open"),"Today Low":p.get("today_low"),"Today High":p.get("today_high")})
    st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.subheader("Latest Closed Trade")
if not closed.empty:
    t=closed.iloc[-1]
    grid([("Stock",t.get("symbol","—")),("Side",t.get("signal",t.get("buy_sell","—"))), ("Entry",t.get("entry","—")),("Exit",t.get("exit_price","—")),("Exit Time",t.get("exit_time","—")),("Exit Reason",t.get("exit_reason","—")),("P&L",f"₹{float(t.get('pnl',0) or 0):,.2f}"),("Quantity",t.get("quantity","—")),("Risk",t.get("actual_risk",t.get("risk","—"))), ("R:R",t.get("rr",t.get("risk_reward","—"))),("PDC",t.get("pdc","—")),("Today Open",t.get("today_open","—")),("Today Low",t.get("today_low","—")),("Today High",t.get("today_high","—")),("Setup",t.get("setup_type","—")),("Sector",t.get("sector",t.get("sector_direction","—"))),("Previous Day",t.get("previous_day_direction","—")),("Market",t.get("market_direction","—"))])
else:st.info("No closed paper trade yet.")
st.subheader("Recent Executed / Capital-Missed Trades")
recent=latest_rows(trades,{"OPEN","CLOSED","MISSED_CAPITAL_OPEN","MISSED_CAPITAL_CLOSED"})
if not recent.empty:st.dataframe(recent,width="stretch",hide_index=True)
else:st.info("No executed or capital-missed trades recorded yet.")
