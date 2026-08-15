import json,sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
INDIA_TZ=ZoneInfo("Asia/Kolkata");NIFTY_THRESHOLD=0.25;ENTRY_START="09:45";ENTRY_END="14:00"
st.set_page_config(page_title="NSE Catalyst | Stock Scanner",page_icon="🔎",layout="wide");st_autorefresh(interval=5000,key="stock_scanner_live");st.markdown(load_css(),unsafe_allow_html=True);render_nav()

def read_json(path):
    try:return json.loads(path.read_text())
    except Exception:return {}
def read_csv(path):
    try:return pd.read_csv(path)
    except Exception:return pd.DataFrame()
def money(v):
    try:return f"₹{float(v):,.2f}"
    except Exception:return "—"
def pct(v):
    try:return f"{float(v):+.2f}%"
    except Exception:return "—"
def metric_cards(items):
    html="<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>" for label,value in items)+"</div>"
    st.markdown(html,unsafe_allow_html=True)

gaps=read_csv(ROOT/"outputs/gap_analysis.csv");waiting=read_json(ROOT/"outputs/waiting_candidates.json");signals=read_csv(ROOT/"outputs/signals.csv");trades=read_csv(ROOT/"outputs/trades.csv");state=read_json(ROOT/"outputs/paper_engine_state.json");diag=read_json(ROOT/"outputs/scanner_diagnostics.json")
try:ensure_bot_running()
except Exception:pass
positions=state.get("open_positions",{}) if isinstance(state,dict) else {};market_change=float(diag.get("nifty500_change_pct",0) or 0);now=datetime.now(INDIA_TZ)
waiting_data=waiting.get("waiting",{}) if isinstance(waiting,dict) else {};qualified_data=waiting.get("qualified",{}) if isinstance(waiting,dict) else {}

st.title("🔎 NIFTY 500 Stock Scanner");st.caption("Complete stock-by-stock view • live waiting states • qualified candidates • entry priority")

# Keep the four workflow KPIs in a true 2×2 layout on both desktop and mobile.
metric_cards([
    ("BUY waiting",len((waiting_data or {}).get("BUY",{}))),
    ("SELL waiting",len((waiting_data or {}).get("SELL",{}))),
    ("BUY qualified",len((qualified_data or {}).get("BUY",{}))),
    ("SELL qualified",len((qualified_data or {}).get("SELL",{}))),
])
st.markdown(f"<div class='dashboard-info-card'><div class='session-row'><span>POSITIONS</span><b>{len(positions)}</b></div></div>",unsafe_allow_html=True)
st.caption(f"NIFTY 500 {market_change:+.2f}% • Control cycle 30s • 1-minute setup data • Updated {now.strftime('%H:%M:%S')} IST")

st.subheader("⏳ Waiting Stocks")
waiting_rows=[]
for side in ("BUY","SELL"):
    for symbol,item in ((waiting_data or {}).get(side,{}) or {}).items():
        waiting_rows.append({"Side":side,"Symbol":symbol,"State":item.get("state","WAITING"),"Today's Open":money(item.get("today_open")),"PDH":money(item.get("pdh")),"PDL":money(item.get("pdl")),"Created":item.get("created_at","—")})
if waiting_rows:st.dataframe(pd.DataFrame(waiting_rows),width="stretch",hide_index=True,height=360)
else:st.info("No stocks are currently waiting for a PDH/PDL breach or Today's Open return.")

st.subheader("🏆 Qualified Candidate Priority")
qualified_rows=[]
for side in ("BUY","SELL"):
    for symbol,item in ((qualified_data or {}).get(side,{}) or {}).items():
        qualified_rows.append({"Side":side,"Symbol":symbol,"Qualified":item.get("qualified_at","—"),"Today's Open":money(item.get("today_open")),"PDH":money(item.get("pdh")),"PDL":money(item.get("pdl"))})
if qualified_rows:st.dataframe(pd.DataFrame(qualified_rows),width="stretch",hide_index=True)
else:st.info("No qualified candidates yet. Once a stock returns to Today's Open after the PDH/PDL breach, it enters the ranking stage.")

st.subheader("📊 Ranking Metrics")
ranks=diag.get("ranking",[]) if isinstance(diag,dict) else []
if ranks:
    rank_df=pd.DataFrame(ranks);rank_df.insert(0,"Priority",range(1,len(rank_df)+1));st.dataframe(rank_df,width="stretch",hide_index=True)
else:st.info("ATR%, RVOL, Beta and traded value appear after candidates qualify.")

st.subheader("📋 Gap / Opening Board")
if gaps.empty:st.info("Gap board will appear when the 1-minute market feed populates it.")
else:
    board=gaps.copy()
    for c in ["TodayOpen","PDH","PDL","Gap","GapPercent"]:
        if c in board.columns:board[c]=pd.to_numeric(board[c],errors="coerce")
    preferred=[c for c in ["Symbol","TodayOpen","PDH","PDL","GapType","GapPercent"] if c in board.columns];view=board[preferred].copy()
    for c in ["TodayOpen","PDH","PDL","Gap"]:
        if c in view.columns:view[c]=view[c].map(money)
    if "GapPercent" in view.columns:view["GapPercent"]=view["GapPercent"].map(pct)
    st.dataframe(view,width="stretch",hide_index=True,height=500)

st.caption("Industry/Sector is not a strategy condition. Entry is based on 1-minute CLOSE state detection, then current market price for execution. Paper trading only.");render_daily_footer()
