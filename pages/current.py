from pathlib import Path
import json
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parent.parent
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
def read_json(p):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {}
def read_csv(p):
    try:return pd.read_csv(p)
    except Exception:return pd.DataFrame()
s=read_json(ROOT/"outputs/bot_status.json"); state=read_json(ROOT/"outputs/paper_engine_state.json"); pos=state.get("open_positions",{}) or {}; trades=read_csv(ROOT/"outputs/trades.csv"); signals=read_csv(ROOT/"outputs/signals.csv")
closed=trades.copy()
if not closed.empty and "status" in closed.columns: closed=closed[closed["status"].astype(str).str.upper().eq("CLOSED")].copy()
if not closed.empty and "pnl" in closed.columns: closed["pnl"]=pd.to_numeric(closed["pnl"],errors="coerce").fillna(0)
realized_pnl=float(closed["pnl"].sum()) if not closed.empty and "pnl" in closed.columns else 0.0
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.55rem .55rem 1.2rem!important}
h1{font-size:1.25rem!important;margin:.1rem 0 .15rem!important}h2{font-size:.9rem!important;margin:.65rem 0 .3rem!important}
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:9px!important;padding:.3rem .4rem!important;min-height:52px!important}
[data-testid="stMetricLabel"]{font-size:.57rem!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:.82rem!important;color:#f4f7fb!important;font-weight:700!important}
@media(max-width:768px){.block-container{padding:.4rem .4rem 1rem!important}h1{font-size:1.05rem!important}h2{font-size:.78rem!important}[data-testid="stMetric"]{min-height:48px!important;padding:.25rem .32rem!important}[data-testid="stMetricValue"]{font-size:.74rem!important}[data-testid="stMetricLabel"]{font-size:.52rem!important}}
</style>
""",unsafe_allow_html=True)
st.title("📌 Current Trading")
st.caption("Live paper positions, current session trades and scanner activity.")
a,b,c,d,e=st.columns(5); a.metric("Bot",s.get("status","UNKNOWN")); b.metric("Worker","ALIVE" if s.get("worker_alive") else "OFFLINE"); c.metric("Open Positions",len(pos)); d.metric("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.0f}"); e.metric("Realized P&L",f"₹{realized_pnl:,.2f}")
st.subheader("Open Positions")
if pos:
 rows=[]
 for symbol,p in pos.items(): rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("risk"),"R:R":p.get("risk_reward",1.25),"Entry Time":p.get("entry_time"),"Setup":p.get("setup_type","GAP_FAILURE_OPEN_RECLAIM")})
 st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else: st.info("No open paper positions.")
st.subheader("Recent Trades")
if not trades.empty: st.dataframe(trades.iloc[::-1].head(30),use_container_width=True,hide_index=True)
else: st.info("No trades recorded yet.")
st.subheader("Latest Scanner Signals")
if not signals.empty: st.dataframe(signals.iloc[::-1].head(30),use_container_width=True,hide_index=True)
else: st.info("No scanner signals yet.")
with st.expander("Diagnostics",expanded=False): st.json({k:s.get(k) for k in ["last_cycle","last_scan","last_scan_completed","scan_count","last_signal_count","scan_duration_seconds","heartbeat","cycle_count","message","error"]})
