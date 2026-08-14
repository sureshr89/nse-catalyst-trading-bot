import json
from pathlib import Path
from datetime import datetime,timezone
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
def heartbeat_alive(value,max_age_seconds=90):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=INDIA_TZ)
        return 0 <= (datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds() <= max_age_seconds
    except Exception:return False
s=read(ROOT/"outputs/bot_status.json","json");state=read(ROOT/"outputs/paper_engine_state.json","json");pos=state.get("open_positions",{}) or {};trades=read(ROOT/"outputs/trades.csv","csv");diag=read(ROOT/"outputs/scanner_diagnostics.json","json")
closed=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
worker=bool(s.get("worker_alive")) and heartbeat_alive(s.get("heartbeat"))
st.title("📌 Current Trading")
st.caption("Only live positions, the latest closed trade and executed/capital-missed records are shown here. Overall performance is on Analysis.")
grid([("Bot",s.get("status","UNKNOWN")),("Worker","ALIVE" if worker else "OFFLINE"),("Open Positions",len(pos)),("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.0f}")])
st.subheader("Open Positions")
if pos:
    rows=[]
    for symbol,p in pos.items():rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("actual_risk",p.get("risk")),"R:R":p.get("rr",p.get("risk_reward",1.25)),"Entry Time":p.get("entry_time"),"Setup":p.get("setup_type","GAP_FAILURE_OPEN_RECLAIM"),"PDC":p.get("pdc"),"Today Open":p.get("today_open"),"Today Low":p.get("today_low"),"Today High":p.get("today_high")})
    st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.subheader("SCANNER FILTER BREAKDOWN")
if diag:
    grid([
        ("Stocks Scanned",diag.get("stocks_scanned",0)),
        ("Liquidity Passed",diag.get("liquidity_passed",0)),
        ("Gap + Previous Day Passed",diag.get("gap_previous_day_passed",0)),
        ("NIFTY Alignment Passed",diag.get("nifty_alignment_passed",0)),
        ("Sector Alignment Passed",diag.get("sector_alignment_passed",0)),
        ("Strategy Setup Passed",diag.get("strategy_setup_passed",0)),
        ("Stock Alignment Passed",diag.get("stock_alignment_passed",0)),
        ("FINAL SIGNALS",diag.get("final_signals",0)),
    ])
    rejections=diag.get("rejections",{}) or {}
    st.subheader("Top Rejection Reasons")
    rejection_labels=[
        ("Sector Alignment", "sector_alignment"),
        ("No Gap Failure", "no_gap_failure"),
        ("No Open Reclaim", "no_open_reclaim"),
        ("Stock Alignment", "stock_alignment"),
        ("Stock Today Direction", "stock_today_direction"),
        ("Strategy Setup", "strategy_setup"),
        ("NIFTY Alignment", "nifty_alignment"),
        ("Gap + Previous Day", "gap_previous_day"),
        ("Missing Data", "missing_data"),
    ]
    ranked=sorted(((label,int(rejections.get(key,0) or 0)) for label,key in rejection_labels),key=lambda x:x[1],reverse=True)
    ranked=[item for item in ranked if item[1]>0]
    if ranked:grid(ranked)
    else:st.info("No rejection reasons recorded yet. The next scanner cycle will populate them.")
else:
    st.info("Scanner filter diagnostics will appear after the next completed scanner cycle.")
st.subheader("Latest Closed Trade")
if not closed.empty:
    t=closed.iloc[-1]
    grid([("Stock",t.get("symbol","—")),("Side",t.get("signal",t.get("buy_sell","—"))), ("Entry",t.get("entry","—")),("Exit",t.get("exit_price","—")),("Exit Time",t.get("exit_time","—")),("Exit Reason",t.get("exit_reason","—")),("P&L",f"₹{float(t.get('pnl',0) or 0):,.2f}"),("Quantity",t.get("quantity","—")),("Risk",t.get("actual_risk",t.get("risk","—"))), ("R:R",t.get("rr",t.get("risk_reward","—"))),("PDC",t.get("pdc","—")),("Today Open",t.get("today_open","—")),("Today Low",t.get("today_low","—")),("Today High",t.get("today_high","—")),("Setup",t.get("setup_type","—")),("Sector",t.get("sector",t.get("sector_direction","—"))),("Previous Day",t.get("previous_day_direction","—")),("Market",t.get("market_direction","—"))])
else:st.info("No closed paper trade yet.")
st.subheader("Recent Executed / Capital-Missed Trades")
recent=latest_rows(trades,{"OPEN","CLOSED","MISSED_CAPITAL_OPEN","MISSED_CAPITAL_CLOSED"})
if not recent.empty:st.dataframe(recent,width="stretch",hide_index=True)
else:st.info("No executed or capital-missed trades recorded yet.")
