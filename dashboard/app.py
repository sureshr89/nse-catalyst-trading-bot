from pathlib import Path
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
ROOT=Path(__file__).resolve().parent.parent
INDIA_TZ=ZoneInfo("Asia/Kolkata"); ENTRY_START="09:45"; ENTRY_END="14:00"; NIFTY_THRESHOLD=0.25
st.set_page_config(page_title="NSE Catalyst | NIFTY 500 Bot",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=5000,key="live"); st.markdown(load_css(),unsafe_allow_html=True)
def load_json(path):
    try:return json.loads(path.read_text())
    except Exception:return {}
def load_csv(path):
    try:return pd.read_csv(path)
    except Exception:return pd.DataFrame()
def grid(items):
    st.markdown('<div class="metric-grid">'+"".join(f'<div class="metric-card"><small>{label}</small><b>{value}</b></div>" for label,value in items)+'</div>',unsafe_allow_html=True)
def heartbeat_alive(value,max_age_seconds=90):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=INDIA_TZ)
        age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds();return 0<=age<=max_age_seconds
    except Exception:return False
render_nav(); status=load_json(ROOT/"outputs/bot_status.json"); state=load_json(ROOT/"outputs/paper_engine_state.json"); diag=load_json(ROOT/"outputs/scanner_diagnostics.json"); signals=load_csv(ROOT/"outputs/signals.csv")
positions=state.get("open_positions",{}) if isinstance(state,dict) else {}
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error:status.setdefault("error",f"Worker launcher: {type(error).__name__}: {error}")
now=datetime.now(INDIA_TZ); worker=bool(status.get("worker_alive",False)) and heartbeat_alive(status.get("heartbeat")); market_change=float(diag.get("nifty500_change_pct",0) or 0) if isinstance(diag,dict) else 0.0
if market_change>=NIFTY_THRESHOLD:permission,permission_note="🟢 BUY ONLY","NIFTY 500 ≥ +0.25%"
elif market_change<=-NIFTY_THRESHOLD:permission,permission_note="🔴 SELL ONLY","NIFTY 500 ≤ −0.25%"
else:permission,permission_note="⚪ WAIT","NIFTY 500 inside −0.25% to +0.25%"
clock=now.strftime("%H:%M"); window="🕘 PREPARE" if clock<ENTRY_START else "🟢 ACTIVE" if clock<=ENTRY_END else "🔒 CLOSED"
st.title("📈 NIFTY 500 Trading Bot"); st.caption("Live command center • PDH/PDL → Today's Open • Paper trading only")
if worker:st.success("🟢 BOT RUNNING • PAPER TRADING")
else:st.warning("🟠 BOT WORKER NOT CONFIRMED ALIVE")
st.subheader("LIVE MARKET DECISION"); grid([("NIFTY 500",f"{market_change:+.2f}%"),("Permission",permission),("Entry Window",window),("Open Positions",len(positions)),("India Time",now.strftime("%H:%M:%S"))]); st.caption(f"{permission_note} • Entries {ENTRY_START}–{ENTRY_END} IST")
if status.get("error"):st.error(str(status["error"]))
st.subheader("🎯 TODAY'S TRADE LOGIC")
st.dataframe(pd.DataFrame([("Universe","NIFTY 500"),("BUY","Today's Open > PDH → price moves below PDH → return above Today's Open"),("SELL","Today's Open < PDL → price moves above PDL → return below Today's Open"),("Market filter","BUY ≥ +0.25% • SELL ≤ −0.25% NIFTY 500")],columns=["Rule","Definition"]),width="stretch",hide_index=True)
st.subheader("🧭 RISK & EXECUTION"); grid([("Universe","NIFTY 500"),("Entry Window","09:45–14:00 IST"),("BUY Stop","PDH"),("SELL Stop","PDL"),("R:R","1 : 1.25"),("Risk / Trade","₹1,400–₹1,500"),("Max Positions","2"),("Daily Max Loss","₹3,000"),("Daily Profit Target","₹5,000"),("Square-off","15:00 IST")])
# Only today's approved signals are shown on the live dashboard.
if not signals.empty:
    date_col="entry_time" if "entry_time" in signals.columns else "timestamp" if "timestamp" in signals.columns else None
    if date_col:
        dates=pd.to_datetime(signals[date_col],errors="coerce")
        if dates.notna().any():
            if getattr(dates.dt,"tz",None) is not None:dates=dates.dt.tz_convert(INDIA_TZ)
            signals=signals.loc[dates.dt.date.eq(now.date())].copy()
st.subheader("📡 TODAY'S APPROVED SIGNALS")
if not signals.empty:
    display=signals.copy()
    if "approved" in display.columns:display=display[display["approved"].astype(str).str.lower().isin(["true","1","yes"])].copy()
    cols=[c for c in ["symbol","signal","entry_time","entry","stop_loss","target","nifty500_change_pct"] if c in display.columns]
    if display.empty or not cols:st.info("No approved qualifying signals today.")
    else:st.dataframe(display[cols].tail(20).iloc[::-1],width="stretch",hide_index=True,height=300)
else:st.info("No approved qualifying signals today.")
if positions:
    st.subheader("📍 OPEN POSITIONS"); rows=[{"Stock":symbol,"Side":str(position.get("signal","")).upper(),"Entry":position.get("entry","—"),"SL":position.get("stop_loss","—"),"Target":position.get("target","—"),"Qty":position.get("quantity","—")} for symbol,position in positions.items()]; st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
st.caption(f"Market-data coverage: {float(diag.get('market_data_coverage',0) or 0)*100:.1f}% • Auto-refresh: 5 seconds"); render_daily_footer()
