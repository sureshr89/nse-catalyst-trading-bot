from pathlib import Path
import json
import pandas as pd
import streamlit as st
from dashboard.nav import render_nav

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
render_nav(8)

def read_json(p):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {}

def read_csv(p):
    try:return pd.read_csv(p)
    except Exception:return pd.DataFrame()

s=read_json(ROOT/"outputs/bot_status.json")
state=read_json(ROOT/"outputs/paper_engine_state.json")
pos=state.get("open_positions",{}) or {}
trades=read_csv(ROOT/"outputs/trades.csv")
worker_alive=bool(s.get("worker_alive")) or bool(s.get("heartbeat"))
bot_status=str((s.get("status") or "WAITING") if worker_alive else "UNKNOWN").upper()
closed=trades.copy()
if not closed.empty and "status" in closed.columns:closed=closed[closed["status"].astype(str).str.upper().eq("CLOSED")].copy()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
realized_pnl=float(closed["pnl"].sum()) if not closed.empty and "pnl" in closed.columns else 0.0

st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.5rem .5rem 1.1rem!important}
h1{font-size:1.18rem!important;margin:.1rem 0 .12rem!important}h2{font-size:.86rem!important;margin:.6rem 0 .28rem!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:.4rem!important}
div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])>div{width:auto!important;min-width:0!important}
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:8px!important;padding:.28rem .35rem!important;min-height:50px!important}
[data-testid="stMetricLabel"]{font-size:.55rem!important;color:#9fb0c7!important;line-height:1.05!important}
[data-testid="stMetricValue"]{font-size:.78rem!important;color:#f4f7fb!important;font-weight:700!important;line-height:1.1!important}
@media(max-width:768px){.block-container{padding:.35rem .35rem .9rem!important}h1{font-size:1rem!important}h2{font-size:.76rem!important}div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:.3rem!important}[data-testid="stMetric"]{min-height:46px!important;padding:.22rem .28rem!important}[data-testid="stMetricLabel"]{font-size:.50rem!important}[data-testid="stMetricValue"]{font-size:.70rem!important}}
</style>
""",unsafe_allow_html=True)

st.title("📌 Current Trading")
st.caption("Live paper positions, current session trades and capital-missed trades.")
a,b,c,d,e=st.columns(5)
a.metric("Bot",bot_status);b.metric("Worker","ALIVE" if worker_alive else "OFFLINE");c.metric("Open Positions",len(pos));d.metric("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.0f}");e.metric("Realized P&L",f"₹{realized_pnl:,.2f}")

st.subheader("Open Positions")
if pos:
 rows=[]
 for symbol,p in pos.items(): rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("risk"),"R:R":p.get("risk_reward",1.25),"Entry Time":p.get("entry_time"),"Setup":p.get("setup_type","GAP_FAILURE_OPEN_RECLAIM")})
 st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:st.info("No open paper positions.")

st.subheader("Recent Executed / Capital-Missed Trades")
if not trades.empty and "status" in trades.columns:
    allowed={"OPEN","CLOSED","MISSED_CAPITAL_OPEN","MISSED_CAPITAL_CLOSED"}
    recent=trades[trades["status"].astype(str).str.upper().isin(allowed)].copy()
    if not recent.empty:st.dataframe(recent.iloc[::-1].head(30),use_container_width=True,hide_index=True)
    else:st.info("No executed or capital-missed trades recorded yet.")
else:st.info("No executed or capital-missed trades recorded yet.")

with st.expander("Diagnostics",expanded=False):
    diag={"Worker":"ALIVE" if worker_alive else "OFFLINE","Status":bot_status,"Heartbeat":s.get("heartbeat") or "—","Last Scan":s.get("last_scan") or "—","Scan Count":s.get("scan_count",0),"Last Completed":s.get("last_scan_completed") or "—","Message":s.get("message") or "—"}
    if s.get("error"):diag["Error"]=s.get("error")
    st.json(diag)
