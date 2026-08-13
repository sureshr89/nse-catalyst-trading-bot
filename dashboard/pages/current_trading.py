import json
from pathlib import Path
import pandas as pd
import streamlit as st
from dashboard.nav import render_nav
ROOT=Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px;min-height:52px}.metric-label{font-size:.58rem;color:#9fb0c7}.metric-value{font-size:.84rem;color:#f4f7fb;font-weight:750;margin-top:3px}
</style>
""",unsafe_allow_html=True)
render_nav(8)
def read(p,kind):
    try:return json.loads(p.read_text()) if kind=="json" else pd.read_csv(p)
    except Exception:return {} if kind=="json" else pd.DataFrame()
s=read(ROOT/"outputs/bot_status.json","json"); state=read(ROOT/"outputs/paper_engine_state.json","json"); pos=state.get("open_positions",{}) or {}; trades=read(ROOT/"outputs/trades.csv","csv"); signals=read(ROOT/"outputs/signals.csv","csv")
closed=trades[trades.get("status",pd.Series(dtype=str)).astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
pnl=float(closed["pnl"].sum()) if not closed.empty and "pnl" in closed.columns else 0
def grid(items):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><div class="metric-label">{a}</div><div class="metric-value">{b}</div></div>' for a,b in items)+'</div>',unsafe_allow_html=True)
st.title("📌 Current Trading")
grid([("Bot",s.get("status","UNKNOWN")),("Worker","ALIVE" if s.get("worker_alive") else "OFFLINE"),("Open Positions",len(pos)),("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.0f}"),("Realized P&L",f"₹{pnl:,.2f}"),("Closed Trades",len(closed))])
st.subheader("Open Positions")
if pos:st.dataframe(pd.DataFrame([{"Stock":k,**v} for k,v in pos.items()]),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.subheader("Recent Trades")
if not trades.empty:st.dataframe(trades.iloc[::-1].head(30),width="stretch",hide_index=True)
else:st.info("No trades recorded yet.")
st.subheader("Latest Scanner Signals")
if not signals.empty:st.dataframe(signals.iloc[::-1].head(30),width="stretch",hide_index=True)
else:st.info("No scanner signals yet.")
