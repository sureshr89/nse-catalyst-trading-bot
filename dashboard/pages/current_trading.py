"""Strategy 1 command center: compact, analysis-first, mobile readable."""
import json,sys
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from bot_runner import ensure_bot_running
from dashboard.nav import render_nav
from dashboard.style import load_css
from market.price_data import PriceData
from strategy.contracts import strategy_metadata
INDIA_TZ=ZoneInfo("Asia/Kolkata"); NIFTY500_TICKER="^CRSLDX"
st.set_page_config(page_title="NSE Catalyst | Strategy 1",page_icon="🔵",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=10000,key="s1_live");st.markdown(load_css(),unsafe_allow_html=True);render_nav()
def read(path,kind="json"):
 try:return json.loads(path.read_text(encoding="utf-8")) if kind=="json" else pd.read_csv(path)
 except Exception:return {} if kind=="json" else pd.DataFrame()
def money(v):
 try:return f"₹{float(v):,.2f}"
 except:return "—"
def pct(v):
 try:return f"{float(v):+.2f}%"
 except:return "—"
def age(v):
 try:
  x=datetime.fromisoformat(str(v).replace("Z","+00:00"));x=x.replace(tzinfo=INDIA_TZ) if x.tzinfo is None else x
  return max(0,int((datetime.now(timezone.utc)-x.astimezone(timezone.utc)).total_seconds()))
 except:return None
def cards(items):st.markdown("<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items)+"</div>",unsafe_allow_html=True)
def aline(label,value,detail):
 st.markdown(f"<div class='s1-analysis-row'><div class='s1-label'>{label}</div><div class='s1-value'>{value}</div><div class='s1-detail'>{detail}</div></div>",unsafe_allow_html=True)
try:launcher=ensure_bot_running() or {}
except Exception as e:launcher={"error":f"Worker launcher: {type(e).__name__}: {e}"}
status=read(ROOT/"outputs/bot_status.json");status.update(launcher if isinstance(launcher,dict) else {})
diag=read(ROOT/"outputs/scanner_diagnostics.json");state=read(ROOT/"outputs/paper_engine_state.json");waiting=read(ROOT/"outputs/waiting_candidates.json");trades=read(ROOT/"outputs/trades.csv","csv")
now=datetime.now(INDIA_TZ);positions=state.get("open_positions",{}) if isinstance(state,dict) else {};scan_age=age(diag.get("timestamp"));hb=age(status.get("heartbeat"));worker_ok=bool(status.get("worker_alive")) and hb is not None and hb<=90
try:
 pdx=PriceData();idx=pdx.get_index_1m(NIFTY500_TICKER);nifty=None if idx.empty else float(idx.iloc[-1]["Close"]);nifty_change=pdx.get_index_change_pct(NIFTY500_TICKER,intraday=idx)
except Exception:pdx=None;nifty,nifty_change=None,None
ad_ratio=diag.get("ad_ratio");coverage=int(diag.get("nifty500_coverage",0) or 0);evaluated=int(diag.get("nifty500_evaluated",diag.get("nifty500_coverage",0)) or 0);total=500
try:ad_ratio=float(ad_ratio) if ad_ratio not in (None,"") else None
except Exception:ad_ratio=None
breadth_complete=bool(diag.get("nifty500_breadth_complete")) and evaluated>=500
meta=strategy_metadata("STRATEGY_1")
st.title("🔵 Strategy 1")
st.caption(f"{meta['name']} • BUY +0.25% / SELL −0.25% • Full NIFTY 500 A/D • previous candle confirmation • live LTP • 10-sec scan • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([("STATUS","🟢 LIVE" if worker_ok else "🔴 STALE"),("NIFTY 500",pct(nifty_change)),("A/D RATIO",f"{ad_ratio:.2f}" if breadth_complete and ad_ratio is not None else "UNAVAILABLE"),("A/D COVERAGE",f"{evaluated}/{total}"),("OPEN TRADES",len(positions)),("LAST SCAN",f"{scan_age}s" if scan_age is not None else "—")])
if not breadth_complete:st.warning(f"NIFTY 500 breadth unavailable: {evaluated}/{total} stocks evaluated. Trading is BLOCKED until 500/500 coverage is available.")
if status.get("error") or status.get("last_scan_error"):st.error(str(status.get("error") or status.get("last_scan_error")))
st.subheader("💼 Live Trade")
if positions:
 rows=[]
 for symbol,p in positions.items():
  try:live=pdx.get_latest_live_price(symbol,max_age_seconds=3);ltp=live.get("Close") if live else None
  except Exception:live,ltp=None,None
  entry=float(p.get("entry") or 0);qty=int(float(p.get("quantity") or 0));side=str(p.get("signal","")).upper();pnl=((float(ltp)-entry)*qty if side=="BUY" else (entry-float(ltp))*qty) if ltp is not None else None
  rows.append({"Stock":symbol,"Side":side,"Entry":money(entry),"LTP":money(ltp),"SL":money(p.get("stop_loss")),"Target":money(p.get("target")),"Qty":qty,"P&L":money(pnl),"Entry Time":p.get("entry_time","—"),"Exit Time":p.get("exit_time","—")})
 st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
else:st.info("No open S1 trade — waiting for a valid setup.")
st.subheader("🧠 Trade Analysis")
with st.expander("1. Before Trade",expanded=True):
 buy_ok=nifty_change is not None and float(nifty_change)>0.25;sell_ok=nifty_change is not None and float(nifty_change)<-0.25;ad_buy=breadth_complete and ad_ratio is not None and ad_ratio>1;ad_sell=breadth_complete and ad_ratio is not None and ad_ratio<1
 aline("BUY MARKET GATE","PASS ✓" if buy_ok else "WAIT",f"NIFTY 500 {pct(nifty_change)} • requires > +0.25%");aline("BUY A/D GATE","PASS ✓" if ad_buy else "BLOCKED",f"A/D {ad_ratio:.2f} • requires > 1 • coverage {evaluated}/500" if breadth_complete and ad_ratio is not None else f"A/D unavailable • coverage {evaluated}/500");aline("SELL MARKET GATE","PASS ✓" if sell_ok else "WAIT",f"NIFTY 500 {pct(nifty_change)} • requires < −0.25%");aline("SELL A/D GATE","PASS ✓" if ad_sell else "BLOCKED",f"A/D {ad_ratio:.2f} • requires < 1 • coverage {evaluated}/500" if breadth_complete and ad_ratio is not None else f"A/D unavailable • coverage {evaluated}/500");aline("BUY CANDLE GATE","PREVIOUS CANDLE GREEN","Previous completed Close > Open");aline("SELL CANDLE GATE","PREVIOUS CANDLE RED","Previous completed Close < Open");aline("BUY SETUP","Open > PDH → Low < PDH → return to Open","BUY immediately at live LTP");aline("SELL SETUP","Open < PDL → High > PDL → return to Open","SELL immediately at live LTP")
with st.expander("2. Entry Confirmation",expanded=True):
 st.markdown("**BUY:** Open > PDH → Low < PDH → price returns to Today's Open → NIFTY 500 > **+0.25%** → A/D > **1** → previous completed candle **GREEN** → **BUY**.");st.markdown("**SELL:** Open < PDL → High > PDL → price returns to Today's Open → NIFTY 500 < **−0.25%** → A/D < **1** → previous completed candle **RED** → **SELL**.");st.caption("All market and breadth conditions must pass at entry. No candle-close entry confirmation; only the previous completed candle is used as the direction filter.")
with st.expander("3. Risk & Target",expanded=True):st.markdown("**BUY SL:** Today's Low at/before entry  •  **SELL SL:** Today's High at/before entry  •  **Target:** 1.25R  •  **Actual risk:** ₹1,400–₹1,500");st.caption("If no quantity fits the ₹1,400–₹1,500 actual-risk band, reject the trade. Never use a future High/Low.")
with st.expander("4. After Trade",expanded=True):
 closed=trades.copy()
 if not closed.empty and "strategy" in closed.columns:closed=closed[closed["strategy"].astype(str).str.upper().isin(["STRATEGY_1","S1","OPEN_RETURN"])]
 cols=[c for c in ["symbol","signal","entry_time","exit_time","entry","exit","stop_loss","target","quantity","actual_risk","pnl","exit_reason"] if c in closed.columns] if not closed.empty else []
 if cols:st.dataframe(closed[cols].tail(20).iloc[::-1],width="stretch",hide_index=True)
 else:st.info("No completed S1 trades yet.")
with st.expander("📋 Candidates",expanded=False):
 rows=[]
 if isinstance(waiting,dict):
  for side in ("BUY","SELL"):
   for state_name in ("waiting","qualified"):
    items=waiting.get(state_name,{}).get(side,{}) if isinstance(waiting.get(state_name,{}),dict) else {}
    for symbol,item in items.items():
     if isinstance(item,dict):rows.append({"Stock":symbol,"Side":side,"State":item.get("state",state_name),"Open":money(item.get("today_open")),"PDH":money(item.get("pdh")),"PDL":money(item.get("pdl"))})
 if rows:st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
 else:st.info("No current S1 candidates.")
with st.expander("📦 More Data",expanded=False):
 cards([("STOCKS SCANNED",diag.get("stocks_scanned",0)),("REFERENCE",diag.get("reference_data_count",0)),("SETUPS",diag.get("opening_setup_passed",0)),("QUALIFIED",diag.get("strategy_setup_passed",0)),("SIGNALS",diag.get("final_signals",0))]);st.json(diag)
with st.expander("⚙️ System / Debug",expanded=False):st.json({"worker":status,"scanner":diag})
st.caption("Fixed S1 format: Live Trade → Analysis → Candidates → More Data → System")
