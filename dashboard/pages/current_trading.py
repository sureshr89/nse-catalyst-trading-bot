import json,sys
from pathlib import Path
from datetime import datetime,timezone
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
from market.price_data import PriceData
INDIA_TZ=ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
st_autorefresh(interval=5000,key="current_live");st.markdown(load_css(),unsafe_allow_html=True);render_nav()
def read(path,kind):
    try:return json.loads(path.read_text()) if kind=="json" else pd.read_csv(path)
    except Exception:return {} if kind=="json" else pd.DataFrame()
def grid(items):st.markdown("<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items)+"</div>",unsafe_allow_html=True)
def heartbeat_alive(value,max_age_seconds=90):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"));stamp=stamp.replace(tzinfo=INDIA_TZ) if stamp.tzinfo is None else stamp;return 0<=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()<=max_age_seconds
    except Exception:return False
status=read(ROOT/"outputs/bot_status.json","json")
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error:status.setdefault("error",f"Worker launcher: {type(error).__name__}: {error}")
state=read(ROOT/"outputs/paper_engine_state.json","json");trades=read(ROOT/"outputs/trades.csv","csv");diag=read(ROOT/"outputs/scanner_diagnostics.json","json");gaps=read(ROOT/"outputs/gap_analysis.csv","csv");pos=state.get("open_positions",{}) if isinstance(state,dict) else {}
closed=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
worker=bool(status.get("worker_alive")) and heartbeat_alive(status.get("heartbeat"))
st.title("📌 Current Trading");st.caption("NIFTY 500 • direct 1-minute price sequence • no candle-pattern confirmation")
grid([("Bot",status.get("status","WAITING")),("Worker","ALIVE" if worker else "OFFLINE"),("Open Positions",len(pos)),("Available Capital",f"₹{float(status.get('available_capital',250000) or 0):,.0f}"),("Last Scan",status.get("last_scan_completed","—")),("Scan Duration",f"{float(status.get('scan_duration_seconds',0) or 0):.1f}s")])
if status.get("error"):st.warning(str(status.get("error")))
market_change=float(diag.get("nifty500_change_pct",0) or 0) if isinstance(diag,dict) else 0.0
market_state="BUY side allowed" if market_change>=0.25 else "SELL side allowed" if market_change<=-0.25 else "NO ENTRY — NIFTY 500 inside ±0.25%"
st.subheader("NIFTY 500 Market Filter");grid([("NIFTY 500 Change",f"{market_change:+.2f}%"),("Filter State",market_state),("Entry Window","09:45–14:00 IST"),("Square-off","15:00 IST")])
st.subheader("Opening Gap Board — strategy levels")
if not gaps.empty and "GapType" in gaps.columns:
    g=gaps.copy();g["GapPercent"]=pd.to_numeric(g.get("GapPercent"),errors="coerce");ups=g[g["GapType"].eq("GAP_UP")].sort_values("GapPercent",ascending=False);downs=g[g["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")
    a,b=st.columns(2)
    with a:st.markdown("**🟢 Gap Up — Today's Open > PDH → BUY setup**");st.dataframe(ups[[c for c in ["Symbol","TodayOpen","PDH","Gap","GapPercent","PreviousClose","PDL"] if c in ups.columns]].head(30),width="stretch",hide_index=True,height=320)
    with b:st.markdown("**🔴 Gap Down — Today's Open < PDL → SELL setup**");st.dataframe(downs[[c for c in ["Symbol","TodayOpen","PDL","Gap","GapPercent","PreviousClose","PDH"] if c in downs.columns]].head(30),width="stretch",hide_index=True,height=320)
else:st.info("Gap board is prepared from current 1-minute data after the market opens.")
st.subheader("Open Positions")
if pos:
    price=PriceData();rows=[]
    for symbol,p in pos.items():
        live=price.get_latest_market_price(symbol);ltp=live.get("Close") if live else None
        rows.append({"Stock":symbol,"Side":p.get("signal",""),"Entry":p.get("entry"),"LTP":ltp,"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("actual_risk",p.get("risk")),"Entry Time":p.get("entry_time"),"PDH":p.get("pdh","—"),"PDL":p.get("pdl","—"),"Today's Open":p.get("today_open","—")})
    st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.subheader("Scanner Filter Breakdown")
if isinstance(diag,dict) and diag:
    grid([("NIFTY 500 Scanned",diag.get("stocks_scanned",0)),("Current 1m Coverage",f"{float(diag.get('market_data_coverage',0) or 0)*100:.1f}%"),("Gap Ups",diag.get("gap_up_count",0)),("Gap Downs",diag.get("gap_down_count",0)),("Gap Setups",diag.get("opening_setup_passed",0)),("NIFTY Filter Passed",diag.get("market_alignment_passed",0)),("Strategy Matches",diag.get("strategy_setup_passed",0)),("FINAL SIGNALS",diag.get("final_signals",0))])
else:st.info("Scanner diagnostics will appear after the next cycle.")
st.subheader("Latest Closed Trade")
if not closed.empty:
    t=closed.iloc[-1];grid([("Stock",t.get("symbol","—")),("Side",t.get("signal","—")),("Entry",t.get("entry","—")),("Exit",t.get("exit_price","—")),("P&L",f"₹{float(t.get('pnl',0) or 0):,.2f}"),("Exit Reason",t.get("exit_reason","—")),("PDH",t.get("pdh","—")),("PDL",t.get("pdl","—")),("Open",t.get("today_open","—")),("Market",t.get("market_direction","—"))])
else:st.info("No closed paper trade yet.")
st.subheader("Recent Trades")
if not trades.empty:st.dataframe(trades.iloc[::-1].head(30),width="stretch",hide_index=True)
else:st.info("No trades recorded yet.")
render_daily_footer()
