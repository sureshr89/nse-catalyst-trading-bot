"""Read-only Strategy 2 analysis. All Strategy 2 charts live only here."""
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.strategy2_data import closed_trades, signals, STARTING_CAPITAL
from strategy.contracts import strategy_metadata

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()
MIN_RISK, MAX_RISK = 1400.0, 1500.0

def chart(fig, key, height=330):
    fig.update_layout(height=height, margin=dict(l=8,r=8,t=48,b=8), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)

def numeric(df, columns):
    for c in columns:
        if c not in df.columns: df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

meta = strategy_metadata("STRATEGY_2")
closed = numeric(closed_trades().copy(), ["pnl","entry","stop_loss","target","quantity","actual_risk","risk_per_share","rr","gap_percent","mae","mfe"])
live = numeric(signals().copy(), ["entry","stop_loss","target","risk_reward","actual_risk","estimated_risk","gap_percent","priority_rank","today_open","today_high","today_low","nifty500_change_pct"])
if not live.empty and "setup_type" in live.columns: live = live[live["setup_type"].astype(str).str.contains("GAP_(UP|DOWN)_EXTENSION_REVERSAL", na=False)].copy()
if not closed.empty:
    closed=closed.reset_index(drop=True); closed["Trade #"]=range(1,len(closed)+1); closed["Result"]=closed["pnl"].map(lambda x:"WIN" if x>0 else "LOSS" if x<0 else "FLAT"); closed["Cumulative P&L"]=closed["pnl"].cumsum(); closed["Peak"]=closed["Cumulative P&L"].cummax(); closed["Drawdown"]=closed["Cumulative P&L"]-closed["Peak"]
if not live.empty:
    live["Gap Magnitude %"]=live["gap_percent"].abs(); live["Actual Risk"]=live["actual_risk"]; live["Risk Band"]=live["Actual Risk"].apply(lambda x:"< ₹1,400" if x<MIN_RISK else "₹1,400–₹1,500" if x<=MAX_RISK else "> ₹1,500")

count=len(closed); wins=int((closed["pnl"]>0).sum()) if count else 0; losses=int((closed["pnl"]<0).sum()) if count else 0; net=float(closed["pnl"].sum()) if count else 0.0; gp=float(closed.loc[closed["pnl"]>0,"pnl"].sum()) if count else 0.0; gl=abs(float(closed.loc[closed["pnl"]<0,"pnl"].sum())) if count else 0.0; win_rate=wins/count*100 if count else 0.0; pf=gp/gl if gl else 0.0; max_dd=abs(float(closed["Drawdown"].min())) if count else 0.0

st.title("📊 Strategy 2 — Complete Analysis")
st.caption(f"{meta['name']} • contract v{meta['version']} • isolated ₹2,50,000 paper capital • read-only — no position changes")
html='<div class="analysis-kpi-grid">'
for label,value in [("Starting Capital",f"₹{STARTING_CAPITAL:,.0f}"),("Decision Records",len(live)),("Closed Trades",count),("Wins / Losses",f"{wins} / {losses}"),("Net P&L",f"₹{net:,.2f}"),("Equity",f"₹{STARTING_CAPITAL+net:,.2f}"),("Win Rate",f"{win_rate:.1f}%"),("Profit Factor",f"{pf:.2f}"),("Max Drawdown",f"₹{max_dd:,.2f}")]: html+=f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
html+='</div>'; st.markdown(html,unsafe_allow_html=True)

with st.expander("⚡ Authoritative Strategy 2 Rules", expanded=False):
    rules=list(meta["rules"])+[("Risk","₹1,400–₹1,500 actual risk • adaptive target ₹1,450 • minimum 1.25R"),("Entry window","09:45–14:00 IST"),("Square-off","15:00 IST")]
    st.dataframe(pd.DataFrame(rules,columns=["Rule","Definition"]),width="stretch",hide_index=True)

st.subheader("📡 Decision Analysis — Signal Journal")
if live.empty:
    st.info("No Strategy 2 decision records are available yet. Charts will populate automatically as the signal journal receives data.")
else:
    approved=live.get("approved",pd.Series(False,index=live.index)).astype(str).str.lower().isin({"true","1","yes"}); live["Outcome"]=approved.map({True:"Approved",False:"Rejected / Watch"})
    a,b=st.columns(2)
    with a: chart(px.bar(live["Outcome"].value_counts().rename_axis("Outcome").reset_index(name="Decisions"),x="Outcome",y="Decisions",text="Decisions",title="Decision Outcome"),"s2_decision_outcome")
    with b:
        side=live["signal"].astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions") if "signal" in live.columns else pd.DataFrame()
        if not side.empty: chart(px.bar(side,x="Signal",y="Decisions",text="Decisions",title="BUY vs SELL Decisions"),"s2_decision_side")
    a,b=st.columns(2)
    with a: chart(px.histogram(live,x="actual_risk",nbins=14,title="Actual Risk Distribution — ₹1,400–₹1,500 band"),"s2_decision_risk")
    with b: chart(px.histogram(live,x="risk_reward",nbins=14,title="Decision Risk:Reward Distribution"),"s2_decision_rr")
    a,b=st.columns(2)
    with a: chart(px.histogram(live,x="Gap Magnitude %",nbins=14,title="Decision GAP Magnitude"),"s2_decision_gap")
    with b:
        scatter=live.dropna(subset=["actual_risk","risk_reward"])
        if not scatter.empty: chart(px.scatter(scatter,x="actual_risk",y="risk_reward",hover_data=[c for c in ["symbol","signal","entry","stop_loss","target","quantity"] if c in scatter.columns],title="Actual Risk vs Risk:Reward"),"s2_decision_risk_rr")
    with st.expander("📋 Decision Records — full signal details",expanded=False):
        cols=[c for c in ["timestamp","symbol","signal","gap_percent","today_open","pdh","pdl","trigger_close","entry","original_stop_loss","stop_loss","target","quantity","actual_risk","risk_reward","risk_adjusted","priority_rank","approved","reason"] if c in live.columns]
        st.dataframe(live[cols].tail(300).iloc[::-1],width="stretch",hide_index=True,height=450)

st.subheader("📈 Closed-Trade Performance")
if closed.empty:
    st.info("No completed Strategy 2 trades yet. The decision analysis above does not require a closed position.")
else:
    tabs=st.tabs(["📌 Overview","💰 P&L","🎯 Setup","🏆 Stocks","📏 GAP","⚖️ Risk / Reward","⏱️ Timing","📋 Trades"])
    with tabs[0]:
        a,b=st.columns(2)
        with a: chart(px.line(closed,x="Trade #",y="Cumulative P&L",markers=True,title="Cumulative P&L"),"s2_cum")
        with b: chart(px.area(closed,x="Trade #",y="Drawdown",title="Drawdown"),"s2_dd")
        a,b=st.columns(2)
        with a: chart(px.pie(closed["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"),names="Result",values="Trades",title="Outcome Mix"),"s2_mix")
        with b: chart(px.bar(closed.groupby("Result",as_index=False)["pnl"].sum(),x="Result",y="pnl",text="pnl",title="P&L by Outcome"),"s2_result")
    with tabs[1]:
        a,b=st.columns(2)
        with a: chart(px.histogram(closed,x="pnl",nbins=14,title="P&L Distribution"),"s2_pnl_dist")
        with b:
            roll=closed[["Trade #","pnl"]].copy(); roll["Rolling Avg"]=roll["pnl"].rolling(5,min_periods=1).mean(); chart(px.line(roll,x="Trade #",y="Rolling Avg",markers=True,title="5-Trade Rolling Average"),"s2_rolling")
    with tabs[2]:
        if "signal" in closed.columns:
            side=closed.groupby("signal",as_index=False).agg(Trades=("pnl","size"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),PnL=("pnl","sum")); a,b=st.columns(2)
            with a: chart(px.bar(side,x="signal",y="Win_Rate",text="Trades",title="Win Rate by Side"),"s2_side_win")
            with b: chart(px.bar(side,x="signal",y="PnL",text="Trades",title="P&L by Side"),"s2_side_pnl")
    with tabs[3]:
        if "symbol" in closed.columns:
            stock=closed.groupby("symbol",as_index=False).agg(Trades=("symbol","size"),PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100)).sort_values("PnL",ascending=False); chart(px.bar(stock.head(20),x="symbol",y="PnL",text="Trades",title="Stocks by P&L"),"s2_stocks",360)
            with st.expander("📋 Stock Performance Table",expanded=False): st.dataframe(stock,width="stretch",hide_index=True,height=360)
    with tabs[4]:
        gap=closed.copy(); gap["Gap Magnitude %"]=gap["gap_percent"].abs(); a,b=st.columns(2)
        with a: chart(px.histogram(gap,x="Gap Magnitude %",nbins=12,title="Opening GAP Magnitude"),"s2_gap_dist")
        with b: chart(px.scatter(gap,x="Gap Magnitude %",y="pnl",hover_data=["symbol","signal"],title="GAP vs P&L"),"s2_gap_pnl")
    with tabs[5]:
        a,b=st.columns(2)
        with a: chart(px.histogram(closed,x="rr",nbins=12,title="Risk:Reward Distribution"),"s2_rr")
        with b:
            riskcol="actual_risk" if closed["actual_risk"].abs().sum() else "risk_per_share"; chart(px.scatter(closed,x=riskcol,y="pnl",hover_data=[c for c in ["symbol","signal","quantity"] if c in closed.columns],title="Actual Risk vs P&L" if riskcol=="actual_risk" else "Risk per Share vs P&L"),"s2_risk")
        band=closed[["actual_risk"]].copy(); band["Risk Band"]=band["actual_risk"].apply(lambda x:"< ₹1,400" if x<1400 else "₹1,400–₹1,500" if x<=1500 else "> ₹1,500"); summary=band.groupby("Risk Band",as_index=False).size().rename(columns={"size":"Trades"}); chart(px.bar(summary,x="Risk Band",y="Trades",text="Trades",title="Actual Risk Band"),"s2_risk_band")
    with tabs[6]:
        if "entry_time" in closed.columns:
            dates=pd.to_datetime(closed["entry_time"],errors="coerce"); dates=dates.dt.tz_localize("Asia/Kolkata") if dates.dt.tz is None else dates.dt.tz_convert("Asia/Kolkata"); timing=pd.DataFrame({"Entry Minute":dates.dt.hour*60+dates.dt.minute,"P&L":closed["pnl"],"RR":closed["rr"]}); a,b=st.columns(2)
            with a: chart(px.scatter(timing,x="Entry Minute",y="P&L",title="Entry Time vs P&L"),"s2_timing")
            with b: chart(px.scatter(timing,x="Entry Minute",y="RR",title="Entry Time vs Risk:Reward"),"s2_timing_rr")
    with tabs[7]:
        with st.expander("📋 Closed Trade Records",expanded=False): st.dataframe(closed.tail(300).iloc[::-1],width="stretch",hide_index=True,height=450)

render_daily_footer()
