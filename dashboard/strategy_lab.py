"""Unified S1-S5 comparison and signal analytics."""
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}

def _read(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def _strategy_col(df):
    if df.empty:return None
    for c in df.columns:
        if str(c).lower().replace(" ","_") in {"strategy","strategy_id","setup","system"}:return c
    return None

def _stats():
    trades=_read("trades.csv");signals=_read("signals.csv");tc=_strategy_col(trades);sc=_strategy_col(signals);rows=[]
    for sid,name in STRATEGIES.items():
        t=trades[trades[tc].astype(str).str.upper().str.startswith(sid)] if tc else pd.DataFrame()
        s=signals[signals[sc].astype(str).str.upper().str.startswith(sid)] if sc else pd.DataFrame()
        rcol=next((c for c in t.columns if str(c).lower() in {"r","r_multiple","net_r","pnl_r"}),None)
        pcol=next((c for c in t.columns if str(c).lower() in {"pnl","p&l","profit_loss","net_pnl"}),None)
        vals=pd.to_numeric(t[rcol],errors="coerce").dropna() if rcol else pd.Series(dtype=float)
        wins=int((vals>0).sum()) if not vals.empty else 0;losses=int((vals<0).sum()) if not vals.empty else 0
        rows.append({"Strategy":sid,"Signals":len(s),"Taken":len(t),"Not Taken":max(len(s)-len(t),0),"Wins":wins,"Losses":losses,"Win Rate":wins/(wins+losses)*100 if wins+losses else None,"Net R":vals.sum() if not vals.empty else None,"Net P&L":pd.to_numeric(t[pcol],errors="coerce").sum() if pcol else None,"Max DD (R)":(vals.cumsum()-vals.cumsum().cummax()).min() if not vals.empty else None})
    return pd.DataFrame(rows)

def render_strategy_lab():
    st.markdown("### ⚖️ S1–S5 strategy comparison")
    d=_stats();display=d.copy();display["Win Rate"]=display["Win Rate"].map(lambda x:f"{x:.1f}%" if pd.notna(x) else "—")
    for c in ["Net R","Net P&L","Max DD (R)"]:display[c]=display[c].map(lambda x:f"{x:.2f}" if pd.notna(x) else "—")
    st.dataframe(display,width="stretch",hide_index=True,height=300)
    if d["Signals"].sum()==0:st.info("No verified signal/trade ledger yet; performance figures will populate from recorded results.")
    else:
        st.markdown("#### Comparison charts")
        st.bar_chart(d.set_index("Strategy")["Win Rate"].fillna(0),height=170)
        st.bar_chart(d.set_index("Strategy")["Net R"].fillna(0),height=170)
        st.bar_chart(d.set_index("Strategy")[["Signals","Taken","Not Taken"]],height=180)
    st.markdown("#### 🎯 Which signal should be picked?")
    st.caption("Do not use first-come-first-served when several strategies signal. Rank signals by confluence first; use signal time only as the final tie-breaker.")
    priority=pd.DataFrame([
        {"Priority":"1","Check":"Master bias alignment","Weight":"30%","Rule":"NIFTY 500 + A/D + sector agree with the signal"},
        {"Priority":"2","Check":"Strategy setup quality","Weight":"30%","Rule":"All mandatory entry/confirmation conditions are satisfied"},
        {"Priority":"3","Check":"Sector confirmation","Weight":"20%","Rule":"Stock sector supports the same direction"},
        {"Priority":"4","Check":"Risk / reward","Weight":"15%","Rule":"Accept only the configured SL/target structure"},
        {"Priority":"5","Check":"Freshness / timing","Weight":"5%","Rule":"If scores tie, take the earliest valid signal"},
    ])
    with st.expander("View signal-picking rules",expanded=False):st.dataframe(priority,width="stretch",hide_index=True)
    st.markdown("#### ⏱️ Signal → Entry → Exit")
    s=_read("signals.csv")
    if not s.empty:
        cols=[c for c in s.columns if str(c).lower() in {"timestamp","time","signal_time","entry_time","exit_time","strategy","strategy_id","signal","side","entry","sl","stop_loss","target","exit","status"}]
        st.dataframe(s[cols].tail(100) if cols else s.tail(100),width="stretch",hide_index=True,height=260)
    else:st.info("No signal timing records yet.")
    st.markdown("#### 📖 Strategy theory & rules")
    theory={"S1":"Sweep PDH/PDL liquidity and reclaim the open.","S2":"Break PDH/PDL, retest the broken level and confirm continuation.","S3":"Sweep the opposite PDH/PDL side and reclaim/reject the open.","S4":"Break a previously formed intraday high/low with confirmation.","S5":"Direct PDH/PDL breakout with previous-candle confirmation."}
    rows=[]
    for sid,name in STRATEGIES.items():rows.append({"Strategy":sid,"Theory":theory[sid],"Entry":"Setup + confirmation","SL":"Setup/swing invalidation","Target":"Configured target","Entry Time":"Configured session window","Square-off":"Configured square-off","Gate":"NIFTY 500 + Sector + A/D; 500/500"})
    with st.expander("View complete S1–S5 theory / rules table",expanded=False):st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True,height=260)
