from pathlib import Path
import json,importlib.util,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
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
status=load(ROOT/"outputs/bot_status.json");state=load(ROOT/"outputs/paper_engine_state.json");trades=load(ROOT/"outputs/trades.csv","csv")
try:
    spec=importlib.util.spec_from_file_location("runner",ROOT/"bot_runner.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    if hasattr(mod,"get_status"):
        live=mod.get_status();status.update(live if isinstance(live,dict) else {})
except Exception as error:
    status.setdefault("error",f"Worker status unavailable: {type(error).__name__}: {error}")

def heartbeat_alive(value,max_age_seconds=90):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return (datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()<=max_age_seconds
    except Exception:return False

def closed_today(df):
    if df.empty or "status" not in df.columns:return pd.DataFrame()
    out=df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if out.empty:return out
    out["pnl"]=pd.to_numeric(out.get("pnl",0),errors="coerce").fillna(0)
    time_col="exit_time" if "exit_time" in out.columns else "entry_time" if "entry_time" in out.columns else None
    if not time_col:return out.iloc[0:0]
    dates=pd.to_datetime(out[time_col],errors="coerce",utc=True).dt.tz_convert("Asia/Kolkata").dt.date
    return out[dates==datetime.now(ZoneInfo("Asia/Kolkata")).date()]

worker=bool(status.get("worker_alive",False)) or heartbeat_alive(status.get("heartbeat"));bot=str(status.get("status","STARTING")).upper()
closed=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
today_closed=closed_today(trades)
overall_wins=int((closed["pnl"]>0).sum()) if not closed.empty else 0
overall_losses=int((closed["pnl"]<0).sum()) if not closed.empty else 0
overall_pnl=float(closed["pnl"].sum()) if not closed.empty and "pnl" in closed.columns else 0.0
today_wins=int((today_closed["pnl"]>0).sum()) if not today_closed.empty else 0
today_losses=int((today_closed["pnl"]<0).sum()) if not today_closed.empty else 0
today_pnl=float(today_closed["pnl"].sum()) if not today_closed.empty else 0.0
today_win_rate=today_wins/len(today_closed)*100 if len(today_closed) else 0.0
if worker and bot=="WAITING":st.warning("🟡 BOT READY • WAITING FOR MARKET SESSION")
elif worker:st.success("🟢 BOT RUNNING • PAPER TRADING")
else:st.warning("🟠 WORKER NOT CONFIRMED ALIVE")

st.subheader("LIVE STATUS");grid([("India Time",datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")),("Bot",bot),("Worker","ALIVE" if worker else "OFFLINE"),("Scanner",status.get("scanner_status","IDLE")),("Open Positions",len(state.get("open_positions",{}) or {})),("Heartbeat",status.get("heartbeat") or "—")])
st.subheader("CAPITAL & RISK");grid([("Starting Capital","₹250,000"),("Available",f"₹{float(status.get('available_capital',250000) or 0):,.0f}"),("Used",f"₹{float(status.get('used_capital',0) or 0):,.0f}"),("Risk / Trade","₹1,400–₹1,500"),("R:R","1:1.25"),("Max Positions",2)])

# Keep today's figures strictly today's figures. Overall performance is shown
# separately so the same P&L/win-rate numbers are not misleadingly repeated.
st.subheader("TODAY'S TRADING");grid([("Closed Trades",len(today_closed)),("Wins / Losses",f"{today_wins} / {today_losses}"),("Win Rate",f"{today_win_rate:.1f}%"),("Today's P&L",f"₹{today_pnl:,.2f}")])
st.subheader("OVERALL PERFORMANCE");grid([("Closed Trades",len(closed)),("Wins / Losses",f"{overall_wins} / {overall_losses}"),("Overall Win Rate",f"{overall_wins/len(closed)*100:.1f}%" if len(closed) else "0.0%"),("Overall P&L",f"₹{overall_pnl:,.2f}")])

st.subheader("LATEST CLOSED TRADE")
if not closed.empty:
    t=closed.iloc[-1]
    grid([("Stock",t.get("symbol","—")),("Side",t.get("signal",t.get("buy_sell","—"))),
          ("Entry",t.get("entry","—")),("Exit",t.get("exit_price","—")),("Exit Time",t.get("exit_time","—")),
          ("Exit Reason",t.get("exit_reason","—")),("P&L",f"₹{float(t.get('pnl',0) or 0):,.2f}"),
          ("Quantity",t.get("quantity","—")),("Risk",t.get("actual_risk",t.get("risk","—"))),
          ("R:R",t.get("rr",t.get("risk_reward","—"))),("PDC",t.get("pdc","—")),
          ("Today Open",t.get("today_open","—")),("Today Low",t.get("today_low","—")),("Today High",t.get("today_high","—")),
          ("Setup",t.get("setup_type","—")),("Sector",t.get("sector",t.get("sector_direction","—"))),
          ("Previous Day",t.get("previous_day_direction","—")),("Market",t.get("market_direction","—"))])
else:st.info("No closed paper trade yet.")

st.subheader("SCANNER ACTIVITY");grid([("Total Scans",status.get("scan_count",0)),("Cycle Count",status.get("cycle_count",0)),("Last Scan",status.get("last_scan") or "—"),("Scan Duration",f'{float(status.get("scan_duration_seconds",0) or 0):.2f}s'),("Last Completed",status.get("last_scan_completed") or "—"),("Last Signal Count",status.get("last_signal_count",0))])
with st.expander("SYSTEM DIAGNOSTICS"):
    st.json({"Last bot cycle":status.get("last_cycle"),"Heartbeat":status.get("heartbeat"),"Worker":worker,"Status":status.get("message") or "—","Last Scan":status.get("last_scan"),"Scan Count":status.get("scan_count",0),"Last Signal Count":status.get("last_signal_count",0),"Last Completed":status.get("last_scan_completed") or "—","Error":status.get("error")})
