from pathlib import Path
import json
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parent.parent
st.set_page_config(page_title="NSE Catalyst | Current Trading",page_icon="📌",layout="wide")
# Keep navigation in the main page area; the sidebar is intentionally unused.
st.markdown("""
<style>
[data-testid="stSidebar"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
.quick-nav{font-size:.72rem;color:#8092aa;margin:.15rem 0 .55rem}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:44px!important;padding:.55rem .4rem!important;border:1px solid #2b3b57!important;border-radius:12px!important;background:#142036!important;color:#e9f0f8!important;font-size:.75rem!important;font-weight:700!important}
@media(max-width:768px){[data-testid="stPageLink"] a{min-height:42px!important;font-size:.62rem!important;padding:.4rem .15rem!important}}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="quick-nav">NSE CATALYST • QUICK NAVIGATION</div>', unsafe_allow_html=True)
n1,n2,n3,n4=st.columns(4,gap="small")
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️")
def read_json(p):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {}
def read_csv(p):
    try:return pd.read_csv(p)
    except Exception:return pd.DataFrame()
s=read_json(ROOT/"outputs/bot_status.json"); state=read_json(ROOT/"outputs/paper_engine_state.json"); pos=state.get("open_positions",{}) or {}; trades=read_csv(ROOT/"outputs/trades.csv"); signals=read_csv(ROOT/"outputs/signals.csv")
st.title("📌 Current Trading")
st.caption("Live paper positions, current session trades and scanner activity.")
a,b,c,d,e=st.columns(5); a.metric("Bot",s.get("status","UNKNOWN")); b.metric("Worker","ALIVE" if s.get("worker_alive") else "OFFLINE"); c.metric("Open Positions",len(pos)); d.metric("Available Capital",f"₹{float(s.get('available_capital',250000) or 0):,.2f}"); e.metric("Daily P&L",f"₹{float(s.get('daily_pnl',0) or 0):,.2f}")
st.subheader("Open Positions")
if pos:
    rows=[]
    for symbol,p in pos.items():rows.append({"Stock":symbol,"Side":str(p.get("signal","")).upper(),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("risk"),"R:R":p.get("risk_reward",1.25),"Entry Time":p.get("entry_time"),"Setup":p.get("setup_type","GAP_FAILURE_OPEN_RECLAIM")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:st.info("No open paper positions.")
st.subheader("Recent Trades")
if not trades.empty:st.dataframe(trades.iloc[::-1].head(30),use_container_width=True,hide_index=True)
else:st.info("No trades recorded yet.")
st.subheader("Latest Scanner Signals")
if not signals.empty:st.dataframe(signals.iloc[::-1].head(30),use_container_width=True,hide_index=True)
else:st.info("No scanner signals yet.")
with st.expander("Diagnostics",expanded=False):st.json({k:s.get(k) for k in ["last_cycle","last_scan","last_scan_completed","scan_count","last_signal_count","scan_duration_seconds","heartbeat","cycle_count","message","error"]})
