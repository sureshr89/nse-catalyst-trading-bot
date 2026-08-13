"""NSE Catalyst Trading Bot - professional live operations dashboard."""
from datetime import datetime
from pathlib import Path
import importlib.util
import json
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
SIGNALS_FILE = PROJECT_ROOT / "outputs" / "signals.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"
BOT_RUNNER_FILE = PROJECT_ROOT / "bot_runner.py"
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.py"
INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst | Live", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=5000, limit=None, key="nse_live_refresh")

st.markdown("""
<style>
.block-container{max-width:1420px;padding:1rem 1.1rem 2.2rem}
[data-testid="stAppViewContainer"]{background:#0b1220}
[data-testid="stHeader"]{background:rgba(11,18,32,.92)}
[data-testid="stMetric"]{background:#111b2d;border:1px solid #26344d;border-radius:12px;padding:.55rem .7rem;min-height:82px}
[data-testid="stMetricLabel"]{font-size:.72rem!important;line-height:1.15!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:1.18rem!important;line-height:1.25!important;font-weight:700!important;color:#f4f7fb!important}
.live-title{font-size:1.55rem;font-weight:800;letter-spacing:-.02em;margin:.1rem 0 .15rem;color:#f5f8fc}
.live-subtitle{font-size:.78rem;color:#9fb0c7;margin-bottom:.7rem}
.section-title{font-size:.92rem;font-weight:750;color:#dce6f3;margin:1rem 0 .45rem}
.nav-note{font-size:.72rem;color:#8092aa;margin:.2rem 0 .65rem}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:44px!important;padding:.55rem .65rem!important;border:1px solid #2b3b57!important;border-radius:12px!important;background:#142036!important;color:#e9f0f8!important;font-size:.78rem!important;font-weight:700!important;text-decoration:none!important;box-shadow:0 2px 8px rgba(0,0,0,.16)!important}
[data-testid="stPageLink"] a:hover{background:#1b2d49!important;border-color:#4d79ad!important;color:#fff!important}
[data-testid="stSidebar"]{background:#0d1728;border-right:1px solid #22314a}
[data-testid="stSidebar"] [data-testid="stPageLink"] a{justify-content:flex-start!important;font-size:.78rem!important;margin:.18rem 0!important}
[data-testid="stDataFrame"]{border:1px solid #26344d;border-radius:10px;overflow:hidden}
.stAlert{border-radius:10px!important}
@media(max-width:768px){
 .block-container{padding:.65rem .55rem 1.5rem}
 .live-title{font-size:1.25rem}
 .live-subtitle{font-size:.7rem;line-height:1.45}
 .section-title{font-size:.86rem}
 [data-testid="stMetric"]{min-height:68px;padding:.45rem .5rem}
 [data-testid="stMetricValue"]{font-size:1rem!important}
 [data-testid="stMetricLabel"]{font-size:.66rem!important}
 [data-testid="stPageLink"] a{min-height:40px!important;font-size:.7rem!important;padding:.45rem .4rem!important}
}
</style>
""", unsafe_allow_html=True)

TOTAL_CAPITAL=250000; MAX_RISK_PER_TRADE=1500; MIN_REQUIRED_RISK=1400; RISK_REWARD_RATIO=1.25
MAX_OPEN_POSITIONS=2; PAPER_TRADING=True; LIVE_TRADING=False; TRADING_START="09:45"; LAST_ENTRY_TIME="14:00"; SQUARE_OFF_TIME="15:00"; SCAN_INTERVAL_SECONDS=30
try:
    spec=importlib.util.spec_from_file_location("nse_current_settings_final",SETTINGS_FILE)
    if spec is None or spec.loader is None: raise ImportError("Could not load config/settings.py")
    settings=importlib.util.module_from_spec(spec); spec.loader.exec_module(settings)
    TOTAL_CAPITAL=int(settings.TOTAL_CAPITAL); MAX_RISK_PER_TRADE=float(settings.MAX_RISK_PER_TRADE); MIN_REQUIRED_RISK=float(settings.MIN_REQUIRED_RISK)
    RISK_REWARD_RATIO=float(settings.RISK_REWARD_RATIO); MAX_OPEN_POSITIONS=int(settings.MAX_OPEN_POSITIONS); PAPER_TRADING=bool(settings.PAPER_TRADING); LIVE_TRADING=bool(settings.LIVE_TRADING)
    TRADING_START=str(settings.TRADING_START); LAST_ENTRY_TIME=str(settings.LAST_ENTRY_TIME); SQUARE_OFF_TIME=str(settings.SQUARE_OFF_TIME); SCAN_INTERVAL_SECONDS=int(settings.SCAN_INTERVAL_SECONDS)
except Exception:
    pass

def read_json(path):
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return {}

def read_csv(path):
    try:return pd.read_csv(path)
    except (FileNotFoundError,pd.errors.EmptyDataError,OSError):return pd.DataFrame()

def dedupe_signals(df):
    if df.empty:return df
    out=df.copy()
    if "timestamp" in out.columns:
        dates=pd.to_datetime(out["timestamp"],errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    else: dates=pd.Series("",index=out.index)
    for col in ["symbol","signal","setup_type"]:
        if col not in out.columns:out[col]=""
    out["_dedupe_key"]=dates+"|"+out["symbol"].astype(str).str.upper().str.strip()+"|"+out["signal"].astype(str).str.upper().str.strip()+"|"+out["setup_type"].astype(str).str.upper().str.strip()
    out=out.drop_duplicates("_dedupe_key",keep="first").drop(columns=["_dedupe_key"])
    return out

def number(data,key,default=0.0):
    try:return float(data.get(key,default) or default)
    except Exception:return float(default)

def fmt_money(value):return f"₹{float(value or 0):,.0f}"
def fmt_time(value):return "—" if not value else str(value).replace("T"," ")[:19]

@st.cache_resource(show_spinner=False)
def load_worker():
    if not BOT_RUNNER_FILE.exists():raise FileNotFoundError(f"Missing worker file: {BOT_RUNNER_FILE}")
    spec=importlib.util.spec_from_file_location("nse_paper_bot_runner_final",BOT_RUNNER_FILE)
    if spec is None or spec.loader is None:raise ImportError("Could not load bot_runner.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    starter=getattr(module,"ensure_bot_running",None)
    if not callable(starter):raise RuntimeError("bot_runner.py does not provide ensure_bot_running().")
    starter(); return module

now=datetime.now(INDIA_TZ); worker_module=None; worker_error=None
try:worker_module=load_worker()
except Exception as exc:worker_error=f"{type(exc).__name__}: {exc}"
bot_status=read_json(STATUS_FILE)
if worker_module is not None:
    try:
        live=worker_module.get_status()
        if isinstance(live,dict):bot_status.update(live)
    except Exception:pass
worker_alive=bool(bot_status.get("worker_alive",False)) if worker_module is not None else False
status=str(bot_status.get("status","STARTING")).upper(); scanner_status=str(bot_status.get("scanner_status","IDLE")).upper()
state=read_json(STATE_FILE); open_positions=state.get("open_positions",{}) or {}; trades=read_csv(TRADES_FILE); signals=dedupe_signals(read_csv(SIGNALS_FILE))

# ----------------------------- NAVIGATION ------------------------------
st.sidebar.markdown("### NSE CATALYST")
st.sidebar.caption("LIVE PAPER-TRADING OPERATIONS")
st.sidebar.divider()
st.sidebar.page_link("app.py",label="🟢  BOT STATUS",icon="🟢")
st.sidebar.page_link("pages/current_trading.py",label="📌  CURRENT TRADING",icon="📌")
st.sidebar.page_link("pages/analysis.py",label="📊  AFTER-TRADING ANALYSIS",icon="📊")
st.sidebar.page_link("pages/downloads.py",label="⬇️  DOWNLOAD FILES",icon="⬇️")
st.sidebar.divider(); st.sidebar.caption(f"Refresh 5s • {now.strftime('%H:%M:%S IST')}")

st.markdown('<div class="live-title">📈 NSE Catalyst</div>',unsafe_allow_html=True)
st.markdown(f'<div class="live-subtitle">NIFTY 100 • Gap-Failure + Open-Reclaim • PAPER ONLY • Entry {TRADING_START}–{LAST_ENTRY_TIME} • Square-off {SQUARE_OFF_TIME}</div>',unsafe_allow_html=True)
st.markdown('<div class="nav-note">Operations are separated from current trades, research and downloads.</div>',unsafe_allow_html=True)

n1,n2,n3,n4=st.columns(4)
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 AFTER-TRADING ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ DOWNLOAD FILES",icon="⬇️")

if worker_error:st.error(f"Worker unavailable: {worker_error}")
elif status=="ERROR":st.error(f"BOT ERROR — {bot_status.get('error') or bot_status.get('message') or 'Unknown worker error'}")
elif status in {"RUNNING","SCANNING"} and worker_alive:st.success("🟢 BOT RUNNING • PAPER TRADING")
elif status=="WAITING" and worker_alive:st.warning("🟡 BOT READY • WAITING FOR MARKET SESSION")
elif worker_alive:st.info("🔵 WORKER ALIVE • STATUS INITIALIZING")
else:st.warning("🟠 WORKER NOT CONFIRMED ALIVE")

st.markdown('<div class="section-title">LIVE STATUS</div>',unsafe_allow_html=True)
a,b,c=st.columns(3); a.metric("India Time",now.strftime("%H:%M:%S")); b.metric("Bot",status); c.metric("Worker","ALIVE" if worker_alive else "OFFLINE")
a,b,c=st.columns(3); a.metric("Scanner",scanner_status); b.metric("Open Positions",len(open_positions)); c.metric("Daily P&L",fmt_money(number(bot_status,"daily_pnl")))

st.markdown('<div class="section-title">CAPITAL & RISK</div>',unsafe_allow_html=True)
a,b,c=st.columns(3); a.metric("Starting Capital",fmt_money(TOTAL_CAPITAL)); b.metric("Available",fmt_money(number(bot_status,"available_capital",TOTAL_CAPITAL))); c.metric("Used",fmt_money(number(bot_status,"used_capital")))
a,b,c=st.columns(3); a.metric("Risk / Trade",f"₹{MIN_REQUIRED_RISK:,.0f}–₹{MAX_RISK_PER_TRADE:,.0f}"); b.metric("R:R",f"1:{RISK_REWARD_RATIO:g}"); c.metric("Max Positions",MAX_OPEN_POSITIONS)

st.markdown('<div class="section-title">OPEN POSITIONS</div>',unsafe_allow_html=True)
if open_positions:
    rows=[]
    for symbol,p in open_positions.items():
        entry=float(p.get("entry",0) or 0); stop=float(p.get("stop_loss",0) or 0); qty=int(float(p.get("quantity",0) or 0))
        rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":entry,"SL":stop,"Target":float(p.get("target",0) or 0),"Qty":qty,"Risk":round(abs(entry-stop)*qty,2),"R:R":p.get("risk_reward",RISK_REWARD_RATIO),"Entry":fmt_time(p.get("entry_time"))})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:st.info("No open paper positions.")

closed=trades.copy()
if not closed.empty and "status" in closed.columns:closed=closed[closed["status"].astype(str).str.upper()=="CLOSED"].copy()
if not closed.empty and "pnl" in closed.columns:closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
wins=int((closed["pnl"]>0).sum()) if not closed.empty else 0; losses=int((closed["pnl"]<0).sum()) if not closed.empty else 0
st.markdown('<div class="section-title">TODAY'S TRADING</div>',unsafe_allow_html=True)
a,b,c=st.columns(3); a.metric("Closed Trades",len(closed)); b.metric("Wins / Losses",f"{wins} / {losses}"); c.metric("Win Rate",f"{wins/len(closed)*100:.1f}%" if len(closed) else "0.0%")
if not closed.empty:
    cols=[c for c in ["trade_id","symbol","signal","entry_time","entry","exit_time","exit_price","exit_reason","quantity","pnl"] if c in closed.columns]; st.dataframe(closed[cols].iloc[::-1].head(12),use_container_width=True,hide_index=True)
else:st.info("No closed trades recorded yet.")

st.markdown('<div class="section-title">SCANNER ACTIVITY</div>',unsafe_allow_html=True)
a,b,c=st.columns(3); a.metric("Total Scans",int(number(bot_status,"scan_count"))); b.metric("Last Signals",len(signals.tail(20)) if not signals.empty else 0); c.metric("Cycle Count",int(number(bot_status,"cycle_count")))
a,b,c=st.columns(3); a.metric("Last Scan",fmt_time(bot_status.get("last_scan"))); b.metric("Scan Duration",f'{number(bot_status,"scan_duration_seconds"):.2f}s'); c.metric("Last Completed",fmt_time(bot_status.get("last_scan_completed")))
if not signals.empty:
    display_cols=[c for c in ["timestamp","symbol","signal","entry","stop_loss","target","approved","reason"] if c in signals.columns]
    st.dataframe(signals[display_cols].iloc[::-1].head(12),use_container_width=True,hide_index=True)
if bot_status.get("last_scan_error"):st.error(f"Last scanner error: {bot_status['last_scan_error']}")

with st.expander("SYSTEM DIAGNOSTICS",expanded=False):
    st.write({"Last bot cycle":fmt_time(bot_status.get("last_cycle")),"Heartbeat":fmt_time(bot_status.get("heartbeat")),"Worker":worker_alive,"Status":bot_status.get("message") or "—"})
with st.expander("STRATEGY CONFIGURATION",expanded=False):
    st.write(f"NIFTY 100 • Pre-09:45: liquidity + previous-day direction + today's gap • GAP_FAILURE_OPEN_RECLAIM • Entry {TRADING_START}–{LAST_ENTRY_TIME} • Square-off {SQUARE_OFF_TIME} • Risk ₹{MIN_REQUIRED_RISK:,.0f}–₹{MAX_RISK_PER_TRADE:,.0f} • R:R 1:{RISK_REWARD_RATIO:g}")
