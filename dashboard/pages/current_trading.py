import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from market.price_data import PriceData
INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END, NIFTY_THRESHOLD = "09:45", "14:00", 0.25
st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="🎯", layout="wide")
st_autorefresh(interval=5000, key="current_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()
def read(path, kind="json"):
    try: return json.loads(path.read_text()) if kind == "json" else pd.read_csv(path)
    except Exception: return {} if kind == "json" else pd.DataFrame()
@st.cache_data(ttl=30, show_spinner=False)
def live_nifty500():
    try:
        pdx=PriceData(); candles=pdx.get_index_1m("^CRSLDX")
        value=None if candles.empty else float(candles.iloc[-1]["Close"])
        change=pdx.get_index_change_pct("^CRSLDX")
        return value, None if change is None else float(change)
    except Exception: return None,None
def price(v):
    try:return f"₹{float(v):,.2f}"
    except Exception:return "—"
def pct(v):
    try:return f"{float(v):+.2f}%"
    except Exception:return "—"
def cards(items):
    st.markdown("<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items)+"</div>",unsafe_allow_html=True)
status=read(ROOT/"outputs/bot_status.json"); state=read(ROOT/"outputs/paper_engine_state.json"); diag=read(ROOT/"outputs/scanner_diagnostics.json"); gaps=read(ROOT/"outputs/gap_analysis.csv","csv"); signals=read(ROOT/"outputs/signals.csv","csv"); waiting=read(ROOT/"outputs/waiting_candidates.json")
try:
    live=ensure_bot_running()
    if isinstance(live,dict):status.update(live)
except Exception as error: status.setdefault("error",f"Worker launcher: {type(error).__name__}: {error}")
positions=state.get("open_positions",{}) if isinstance(state,dict) else {}
nifty_value,live_change=live_nifty500(); raw=diag.get("nifty500_change_pct")
market_change=live_change if live_change is not None else (None if raw in (None,"") else float(raw))
now=datetime.now(INDIA_TZ); clock=now.strftime("%H:%M")
permission="🟢 BUY" if market_change is not None and market_change>=NIFTY_THRESHOLD else "🔴 SELL" if market_change is not None and market_change<=-NIFTY_THRESHOLD else "⚪ WAIT"
window="PREPARE" if clock<ENTRY_START else "ACTIVE" if clock<=ENTRY_END else "CLOSED"
st.title("🎯 Current Trading")
st.caption("Live strategy command center • largest qualifying GAP first • PDH/PDL SL • paper trading")
cards([("NIFTY 500 VALUE",price(nifty_value) if nifty_value is not None else "Unavailable"),("NIFTY 500 CHANGE",pct(market_change) if market_change is not None else "Unavailable"),("Market Permission",permission),("Entry Window",window),("Open Positions",len(positions))])
st.caption(f"Control cycle 30s • completed 1m data • Entries {ENTRY_START}–{ENTRY_END} IST • Updated {now.strftime('%H:%M:%S')} IST")
if status.get("error"):st.warning(str(status["error"]))

st.subheader("🔍 Trade Decision Diagnostics")
d=diag if isinstance(diag,dict) else {}
rejections=d.get("rejections",{}) if isinstance(d.get("rejections",{}),dict) else {}
metric_rows=[
    ("Stocks scanned",d.get("stocks_scanned",0)),("Gap candidates",d.get("gap_data_count",0)),("Opening setup passed",d.get("opening_setup_passed",0)),
    ("Market alignment passed",d.get("market_alignment_passed",0)),("Strategy setup passed",d.get("strategy_setup_passed",0)),("Final signals",d.get("final_signals",0)),
    ("BUY waiting",d.get("buy_waiting",0)),("SELL waiting",d.get("sell_waiting",0)),("BUY qualified",d.get("buy_qualified",0)),("SELL qualified",d.get("sell_qualified",0)),
]
metric_df=pd.DataFrame(metric_rows,columns=["Stage","Count"]); metric_df["Stage"]=metric_df["Stage"].astype(str); metric_df["Count"]=pd.to_numeric(metric_df["Count"],errors="coerce").fillna(0).astype(int)
st.dataframe(metric_df,width="stretch",hide_index=True)
reason_rows=[(str(k).replace("_"," ").title(),pd.to_numeric(pd.Series([v]),errors="coerce").fillna(0).iloc[0]) for k,v in rejections.items()]
if reason_rows:
    reason_df=pd.DataFrame(reason_rows,columns=["Rejection reason","Count"]);reason_df["Rejection reason"]=reason_df["Rejection reason"].astype(str);reason_df["Count"]=pd.to_numeric(reason_df["Count"],errors="coerce").fillna(0).astype(int);st.dataframe(reason_df,width="stretch",hide_index=True)
rank=d.get("ranking",[]) if isinstance(d.get("ranking",[]),list) else []
if rank:
    st.markdown("**Current highest-GAP qualified priority:**")
    rank_df=pd.DataFrame(rank[:15]);
    for col in rank_df.columns: rank_df[col]=rank_df[col].map(lambda x: "" if pd.isna(x) else str(x))
    st.dataframe(rank_df,width="stretch",hide_index=True)
else: st.info("No final qualified signal has reached the entry gate yet. The counters above show exactly where candidates are stopping.")
st.caption(f"Scanner: {status.get('scanner_status','—')} • Last scan: {status.get('last_scan_completed','—')} • Last error: {status.get('last_scan_error') or 'None'}")

st.subheader("⚡ Strategy State")
st.dataframe(pd.DataFrame([("BUY","Open > PDH → completed 1m close below PDH → later completed 1m close back to Today's Open"),("SELL","Open < PDL → completed 1m close above PDL → later completed 1m close back to Today's Open"),("Entry","Final NIFTY confirmation + stock at/above Open for BUY or at/below Open for SELL → current market price"),("Priority","Largest qualifying absolute Gap % first"),("Stop loss","BUY = PDH • SELL = PDL"),("Risk","₹1,400–₹1,500 per trade • Target 1.25R • Max 2")],columns=["Condition","Current Rule"]),width="stretch",hide_index=True)

st.subheader("⏳ Live Waiting Stocks")
wc=waiting.get("waiting",{}) if isinstance(waiting,dict) else {}; rows=[]
for side in ("BUY","SELL"):
    for symbol,item in (wc.get(side,{}) or {}).items():rows.append({"Side":side,"Stock":symbol,"State":item.get("state","WAITING"),"Gap %":item.get("gap_percent",0),"Today's Open":price(item.get("today_open")),"PDH":price(item.get("pdh")),"PDL":price(item.get("pdl"))})
if rows:
    wdf=pd.DataFrame(rows);wdf["Gap %"]=pd.to_numeric(wdf["Gap %"],errors="coerce");wdf=wdf.sort_values("Gap %",key=lambda s:s.abs(),ascending=False);st.dataframe(wdf,width="stretch",hide_index=True,height=300)
else:st.info("No stocks currently waiting for a PDH/PDL breach or Today's Open return.")

st.subheader("🏆 Qualified Priority")
qc=waiting.get("qualified",{}) if isinstance(waiting,dict) else {};qrows=[]
for side in ("BUY","SELL"):
    for symbol,item in (qc.get(side,{}) or {}).items():qrows.append({"Side":side,"Stock":symbol,"Qualified":item.get("qualified_at","—"),"Gap %":item.get("gap_percent",0),"Today's Open":price(item.get("today_open")),"PDH":price(item.get("pdh")),"PDL":price(item.get("pdl"))})
if qrows:
    qdf=pd.DataFrame(qrows);qdf["Gap %"]=pd.to_numeric(qdf["Gap %"],errors="coerce");qdf=qdf.sort_values("Gap %",key=lambda s:s.abs(),ascending=False);st.dataframe(qdf,width="stretch",hide_index=True)
else:st.info("No qualified candidates yet.")

st.subheader("🎯 Gap Candidates")
if not gaps.empty and "GapType" in gaps.columns:
    board=gaps.copy()
    for c in ["TodayOpen","PDH","PDL","Gap","GapPercent"]:
        if c in board.columns:board[c]=pd.to_numeric(board[c],errors="coerce")
    board["GapPriority"]=board["GapPercent"].abs() if "GapPercent" in board.columns else 0;ups=board[board["GapType"].eq("GAP_UP")].sort_values("GapPriority",ascending=False);downs=board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPriority",ascending=False);cards([("Gap Up",len(ups)),("Gap Down",len(downs)),("Total Candidates",len(ups)+len(downs))]);c1,c2=st.columns(2,gap="large")
    for frame,title,level,container in [(ups,"### 🟢 BUY WATCHLIST — LARGEST GAP FIRST","PDH",c1),(downs,"### 🔴 SELL WATCHLIST — LARGEST GAP FIRST","PDL",c2)]:
        with container:
            st.markdown(title);view=frame[[c for c in ["Symbol","TodayOpen",level,"GapPercent"] if c in frame.columns]].head(30).copy()
            if view.empty:st.info("No candidates.")
            else:
                for c in ["TodayOpen",level]:
                    if c in view.columns:view[c]=view[c].map(price)
                if "GapPercent" in view.columns:view["GapPercent"]=view["GapPercent"].map(pct)
                st.dataframe(view,width="stretch",hide_index=True,height=300)
else:st.info("Today's gap board is not available yet.")

st.subheader("🚨 Today's Approved Signals")
if not signals.empty:
    date_col="entry_time" if "entry_time" in signals.columns else "timestamp" if "timestamp" in signals.columns else None
    if date_col:
        dates=pd.to_datetime(signals[date_col],errors="coerce")
        if dates.notna().any():dates=dates.dt.tz_convert(INDIA_TZ) if getattr(dates.dt,"tz",None) is not None else dates.dt.tz_localize(INDIA_TZ);signals=signals.loc[dates.dt.date.eq(now.date())].copy()
    approved=signals.copy()
    if "approved" in approved.columns:approved=approved[approved["approved"].astype(str).str.lower().isin(["true","1","yes"])]
    cols=[c for c in ["symbol","signal","entry_time","entry","stop_loss","target","quantity","gap_percent","priority_rank"] if c in approved.columns]
    if not approved.empty and cols:st.dataframe(approved[cols].tail(20).iloc[::-1],width="stretch",hide_index=True,height=300)
    else:st.info("No approved signals today.")
else:st.info("No approved signals today.")

st.subheader("📍 Open Positions")
if positions:
    price_data=PriceData();rows=[]
    for symbol,position in positions.items():
        try:latest=price_data.get_latest_market_price(symbol);ltp=latest.get("Close") if latest else None
        except Exception:ltp=None
        entry=position.get("entry");side=str(position.get("signal","")).upper();pnl=None
        try:qty=float(position.get("quantity",0) or 0);pnl=((float(ltp)-float(entry))*qty if side=="BUY" else (float(entry)-float(ltp))*qty) if ltp is not None and entry is not None else None
        except Exception:pass
        rows.append({"Stock":symbol,"Side":side,"Entry":price(entry),"LTP":price(ltp),"Live P&L":price(pnl),"SL":price(position.get("stop_loss")),"Target":price(position.get("target")),"Qty":position.get("quantity","—"),"Gap %":pct(position.get("gap_percent"))})
    st.dataframe(pd.DataFrame(rows).astype(str),width="stretch",hide_index=True)
else:st.info("No open paper positions.")
st.caption("Auto-refresh 5s • control cycle 30s • completed market data 1m • Paper trading only")
render_daily_footer()
