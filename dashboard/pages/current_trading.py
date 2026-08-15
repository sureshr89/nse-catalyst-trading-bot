import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from market.price_data import PriceData
INDIA_TZ=ZoneInfo("Asia/Kolkata")
ENTRY_START="09:45"; ENTRY_END="14:00"; NIFTY_THRESHOLD=0.25
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="🎯",layout="wide")
st_autorefresh(interval=5000,key="current_live")
st.markdown(load_css(),unsafe_allow_html=True); render_nav()
def read(path,kind="json"):
    try:return json.loads(path.read_text()) if kind=="json" else pd.read_csv(path)
    except Exception:return {} if kind=="json" else pd.DataFrame()
def cards(items):
    html="<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items)+"</div>"; st.markdown(html,unsafe_allow_html=True)
def price(v):
    try:return f"₹{float(v):,.2f}"
    except Exception:return "—"
def pct(v):
    try:return f"{float(v):+.2f}%"
    except Exception:return "—"
status=read(ROOT/"outputs/bot_status.json"); state=read(ROOT/"outputs/paper_engine_state.json"); diag=read(ROOT/"outputs/scanner_diagnostics.json"); gaps=read(ROOT/"outputs/gap_analysis.csv","csv"); signals=read(ROOT/"outputs/signals.csv","csv")
positions=state.get("open_positions",{}) if isinstance(state,dict) else {}
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error:status.setdefault("error",f"Worker launcher: {type(error).__name__}: {error}")
now=datetime.now(INDIA_TZ); clock=now.strftime("%H:%M"); market_change=float(diag.get("nifty500_change_pct",0) or 0) if isinstance(diag,dict) else 0.0
permission="🟢 BUY" if market_change>=NIFTY_THRESHOLD else "🔴 SELL" if market_change<=-NIFTY_THRESHOLD else "⚪ WAIT"; window="PREPARE" if clock<ENTRY_START else "ACTIVE" if clock<=ENTRY_END else "CLOSED"
st.title("🎯 Current Trading"); st.caption("Live strategy command center • today's candidates, approved signals and open positions")
cards([("NIFTY 500",pct(market_change)),("Market Permission",permission),("Entry Window",window),("Open Positions",len(positions))]); st.caption(f"Entries {ENTRY_START}–{ENTRY_END} IST • Updated {now.strftime('%H:%M:%S')} IST")
if status.get("error"):st.warning(str(status["error"]))
st.subheader("⚡ Strategy State")
st.dataframe(pd.DataFrame([("Universe","NIFTY 500"),("BUY","Open above PDH → price moves below PDH → return above Today's Open"),("SELL","Open below PDL → price moves above PDL → return below Today's Open"),("Market filter","BUY ≥ +0.25% • SELL ≤ −0.25% NIFTY 500"),("Risk","SL = PDH/PDL • Target = 1.25 × entry-to-SL risk")],columns=["Condition","Current Rule"]),width="stretch",hide_index=True)
st.subheader("🎯 Gap Candidates")
if not gaps.empty and "GapType" in gaps.columns:
    board=gaps.copy()
    for col in ["TodayOpen","PDH","PDL","Gap","GapPercent"]:
        if col in board.columns:board[col]=pd.to_numeric(board[col],errors="coerce")
    ups=board[board["GapType"].eq("GAP_UP")].sort_values("GapPercent",ascending=False); downs=board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")
    cards([("Gap Up",len(ups)),("Gap Down",len(downs)),("Total Candidates",len(ups)+len(downs))]); c1,c2=st.columns(2,gap="large")
    with c1:
        st.markdown("### 🟢 BUY WATCHLIST")
        if ups.empty:st.info("No gap-up candidates.")
        else:
            cols=[c for c in ["Symbol","TodayOpen","PDH","GapPercent"] if c in ups.columns];view=ups[cols].head(30).copy()
            for c in ["TodayOpen","PDH"]:
                if c in view.columns:view[c]=view[c].map(price)
            if "GapPercent" in view.columns:view["GapPercent"]=view["GapPercent"].map(pct)
            st.dataframe(view,width="stretch",hide_index=True,height=330)
    with c2:
        st.markdown("### 🔴 SELL WATCHLIST")
        if downs.empty:st.info("No gap-down candidates.")
        else:
            cols=[c for c in ["Symbol","TodayOpen","PDL","GapPercent"] if c in downs.columns];view=downs[cols].head(30).copy()
            for c in ["TodayOpen","PDL"]:
                if c in view.columns:view[c]=view[c].map(price)
            if "GapPercent" in view.columns:view["GapPercent"]=view["GapPercent"].map(pct)
            st.dataframe(view,width="stretch",hide_index=True,height=330)
else:st.info("Today's gap board is not available yet.")
# Live page shows only today's approved signals.
if not signals.empty:
    date_col="entry_time" if "entry_time" in signals.columns else "timestamp" if "timestamp" in signals.columns else None
    if date_col:
        dates=pd.to_datetime(signals[date_col],errors="coerce")
        if dates.notna().any():
            if getattr(dates.dt,"tz",None) is not None:dates=dates.dt.tz_convert(INDIA_TZ)
            signals=signals.loc[dates.dt.date.eq(now.date())].copy()
st.subheader("🚨 Today's Approved Signals")
if signals.empty:st.info("No approved signals today.")
else:
    approved=signals.copy()
    if "approved" in approved.columns:approved=approved[approved["approved"].astype(str).str.lower().isin(["true","1","yes"])].copy()
    cols=[c for c in ["symbol","signal","entry_time","entry","stop_loss","target","nifty500_change_pct"] if c in approved.columns]
    if approved.empty or not cols:st.info("No approved signals today.")
    else:st.dataframe(approved[cols].tail(20).iloc[::-1],width="stretch",hide_index=True,height=260)
st.subheader("📍 Open Positions")
if positions:
    price_data=PriceData();rows=[]
    for symbol,pos in positions.items():
        try:latest=price_data.get_latest_market_price(symbol);ltp=latest.get("Close") if latest else None
        except Exception:ltp=None
        entry=pos.get("entry");side=str(pos.get("signal","")).upper();pnl=None
        try:
            qty=float(pos.get("quantity",0) or 0)
            if ltp is not None and entry is not None:pnl=(float(ltp)-float(entry))*qty if side=="BUY" else (float(entry)-float(ltp))*qty
        except Exception:pass
        rows.append({"Stock":symbol,"Side":side,"Entry":price(entry),"LTP":price(ltp),"Live P&L":price(pnl),"SL":price(pos.get("stop_loss")),"Target":price(pos.get("target")),"Qty":pos.get("quantity","—")})
    st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.caption("Auto-refresh: 5 seconds • Paper trading only"); render_daily_footer()
