"""Strategy 1 single-page command center."""
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
st_autorefresh(interval=5000,key="s1_live");st.markdown(load_css(),unsafe_allow_html=True);render_nav()
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
 st.markdown(f"<div class='s1-analysis-row'><div class='s1-label'>{label}</div><div class='s1-value'>{value}</div><div class='s1-detail'>{detail}</div></div>")
try:launcher=ensure_bot_running() or {}
except Exception as e:launcher={"error":f"Worker launcher: {type(e).__name__}: {e}"}
status=read(ROOT/"outputs/bot_status.json");status.update(launcher if isinstance(launcher,dict) else {})
diag=read(ROOT/"outputs/scanner_diagnostics.json");state=read(ROOT/"outputs/paper_engine_state.json");waiting=read(ROOT/"outputs/waiting_candidates.json");trades=read(ROOT/"outputs/trades.csv","csv")
now=datetime.now(INDIA_TZ);positions=state.get("open_positions",{}) if isinstance(state,dict) else {};scan_age=age(diag.get("timestamp"));hb=age(status.get("heartbeat"));worker_ok=bool(status.get("worker_alive")) and hb is not None and hb<=90
try:
 pdx=PriceData();idx=pdx.get_index_1m(NIFTY500_TICKER);nifty=None if idx.empty else float(idx.iloc[-1]["Close"]);nifty_change=pdx.get_index_change_pct(NIFTY500_TICKER,intraday=idx)
except Exception:pdx=None;nifty,nifty_change=None,None
ad_ratio=None
for key in ("ad_ratio","advance_decline_ratio","adv_dec_ratio","a_d_ratio"):
 try:
  if key in diag and diag[key] not in (None,""):ad_ratio=float(diag[key]);break
 except Exception:pass
adv=diag.get("advances",diag.get("advance_count"));dec=diag.get("declines",diag.get("decline_count"))
if ad_ratio is None and adv is not None and dec not in (None,0):
 try:ad_ratio=float(adv)/float(dec)
 except Exception:pass
meta=strategy_metadata("STRATEGY_1")
st.title("🔵 Strategy 1");st.caption(f"{meta['name']} • {meta['version']} • Live LTP • immediate entry/exit • no candle-close • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([("STATUS","🟢 LIVE" if worker_ok else "🔴 STALE"),("NIFTY 500",pct(nifty_change)),("A/D RATIO",f"{ad_ratio:.2f}" if ad_ratio is not None else "—"),("OPEN TRADES",len(positions)),("DAILY P&L",money(status.get("daily_pnl",status.get("session_pnl",0)))),("LAST SCAN",f"{scan_age}s" if scan_age is not None else "—")])
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
else:st.info("No open S1 trade — waiting for the exact live setup.")
st.subheader("🧠 Trade Analysis")
with st.expander("1. Before Trade",expanded=True):
 buy_ok=nifty_change is not None and float(nifty_change)>0;sell_ok=nifty_change is not None and float(nifty_change)<0;ad_buy=ad_ratio is not None and ad_ratio>1;ad_sell=ad_ratio is not None and ad_ratio<1
 aline("BUY MARKET GATE","PASS ✓" if buy_ok else "WAIT",f"NIFTY 500 {pct(nifty_change)} • requires > 0%");aline("BUY A/D GATE","PASS ✓" if ad_buy else "WAIT",f"A/D {ad_ratio:.2f} • requires > 1" if ad_ratio is not None else "A/D unavailable");aline("SELL MARKET GATE","PASS ✓" if sell_ok else "WAIT",f"NIFTY 500 {pct(nifty_change)} • requires < 0%");aline("SELL A/D GATE","PASS ✓" if ad_sell else "WAIT",f"A/D {ad_ratio:.2f} • requires < 1" if ad_ratio is not None else "A/D unavailable");aline("BUY SETUP","Open > PDH → Low < PDH → return to Open","Immediate BUY • no candle close");aline("SELL SETUP","Open < PDL → High > PDL → return to Open","Immediate SELL • no candle close")
with st.expander("2. Entry Confirmation",expanded=True):
 st.markdown("**BUY**  Open > PDH → Low < PDH → price returns to Today's Open → NIFTY 500 > 0% + A/D > 1 → **BUY immediately**.");st.markdown("**SELL**  Open < PDL → High > PDL → price returns to Today's Open → NIFTY 500 < 0% + A/D < 1 → **SELL immediately**.");st.caption("SL uses only Today's Low/High recorded before or at entry. No future value is used.")
with st.expander("3. Risk & Target",expanded=True):st.markdown("**SL:** Today's Low (BUY) / Today's High (SELL)  •  **Target:** 1.25R  •  **Actual risk:** ₹1,400–₹1,500");st.caption("If no quantity produces ₹1,400–₹1,500 actual risk, reject the trade.")
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