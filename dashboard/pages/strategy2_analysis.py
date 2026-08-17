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
from dashboard.strategy2_data import closed_trades, STARTING_CAPITAL
from strategy.contracts import strategy_metadata

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

def chart(fig, key):
    fig.update_layout(height=330, margin=dict(l=8, r=8, t=48, b=8), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)

df = closed_trades()
if not df.empty:
    for c in ["pnl", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_per_share", "rr", "gap_percent", "mae", "mfe"]:
        if c not in df.columns: df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df = df.reset_index(drop=True); df["Trade #"] = range(1, len(df) + 1); df["Result"] = df["pnl"].map(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT"); df["Cumulative P&L"] = df["pnl"].cumsum(); df["Peak"] = df["Cumulative P&L"].cummax(); df["Drawdown"] = df["Cumulative P&L"] - df["Peak"]
else: df = pd.DataFrame()

count = len(df); wins = int((df["pnl"] > 0).sum()) if count else 0; losses = int((df["pnl"] < 0).sum()) if count else 0; net = float(df["pnl"].sum()) if count else 0.0; gross_profit = float(df.loc[df["pnl"] > 0, "pnl"].sum()) if count else 0.0; gross_loss = abs(float(df.loc[df["pnl"] < 0, "pnl"].sum())) if count else 0.0; win_rate = wins / count * 100 if count else 0.0; profit_factor = gross_profit / gross_loss if gross_loss else 0.0; max_dd = abs(float(df["Drawdown"].min())) if count else 0.0
meta = strategy_metadata("STRATEGY_2")

st.title("📊 Strategy 2 — Complete Analysis")
st.caption(f"{meta['name']} • contract v{meta['version']} • isolated ₹2,50,000 paper capital")
html = '<div class="analysis-kpi-grid">'
for label, value in [("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"),("Closed Trades", count),("Wins / Losses", f"{wins} / {losses}"),("Net P&L", f"₹{net:,.2f}"),("Equity", f"₹{STARTING_CAPITAL + net:,.2f}"),("Win Rate", f"{win_rate:.1f}%"),("Profit Factor", f"{profit_factor:.2f}"),("Max Drawdown", f"₹{max_dd:,.2f}")]: html += f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
html += "</div>"; st.markdown(html, unsafe_allow_html=True)

st.subheader("⚡ Authoritative Rules")
st.dataframe(pd.DataFrame(meta["rules"], columns=["Rule", "Definition"]), width="stretch", hide_index=True)

if df.empty:
    st.info("No completed Strategy 2 trades yet.")
else:
    tabs = st.tabs(["📌 Overview", "💰 P&L", "🏆 Stocks", "📏 GAP", "⚖️ Risk", "⏱️ Timing", "📋 Trades"])
    with tabs[0]:
        a,b=st.columns(2)
        with a: chart(px.line(df,x="Trade #",y="Cumulative P&L",markers=True,title="Cumulative P&L"),"s2_cum")
        with b: chart(px.area(df,x="Trade #",y="Drawdown",title="Drawdown"),"s2_dd")
        a,b=st.columns(2)
        with a: chart(px.pie(df["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"),names="Result",values="Trades",title="Outcome Mix"),"s2_mix")
        with b: chart(px.bar(df.groupby("Result",as_index=False)["pnl"].sum(),x="Result",y="pnl",text="pnl",title="P&L by Outcome"),"s2_result")
    with tabs[1]:
        a,b=st.columns(2)
        with a: chart(px.histogram(df,x="pnl",nbins=14,title="P&L Distribution"),"s2_dist")
        with b:
            roll=df[["Trade #","pnl"]].copy(); roll["Rolling Avg"]=roll["pnl"].rolling(5,min_periods=1).mean(); chart(px.line(roll,x="Trade #",y="Rolling Avg",markers=True,title="5-Trade Rolling Average"),"s2_roll")
    with tabs[2]:
        if "symbol" not in df.columns: st.info("No stock-level results yet.")
        else:
            stock=df.groupby("symbol",as_index=False).agg(Trades=("symbol","size"),PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100)).sort_values("PnL",ascending=False); chart(px.bar(stock.head(20),x="symbol",y="PnL",text="Trades",title="Stocks by P&L"),"s2_stocks"); st.dataframe(stock,width="stretch",hide_index=True)
    with tabs[3]:
        gap=df.copy(); gap["Gap Magnitude %"]=gap["gap_percent"].abs(); a,b=st.columns(2)
        with a: chart(px.histogram(gap,x="Gap Magnitude %",nbins=12,title="Opening GAP Magnitude"),"s2_gap_dist")
        with b: chart(px.scatter(gap,x="Gap Magnitude %",y="pnl",hover_data=["symbol","signal"],title="GAP vs P&L"),"s2_gap_pnl")
    with tabs[4]:
        a,b=st.columns(2)
        with a: chart(px.histogram(df,x="rr",nbins=12,title="Recorded Risk:Reward"),"s2_rr")
        with b: chart(px.scatter(df,x="risk_per_share",y="pnl",hover_data=["symbol","signal"],title="Risk per Share vs P&L"),"s2_risk")
    with tabs[5]:
        if "entry_time" not in df.columns: st.info("No timing results yet.")
        else:
            dates=pd.to_datetime(df["entry_time"],errors="coerce"); dates=dates.dt.tz_localize("Asia/Kolkata") if getattr(dates.dt,"tz",None) is None else dates.dt.tz_convert("Asia/Kolkata"); timing=pd.DataFrame({"Entry Minute":dates.dt.hour*60+dates.dt.minute,"P&L":df["pnl"]}); chart(px.scatter(timing,x="Entry Minute",y="P&L",title="Entry Time vs P&L"),"s2_timing")
    with tabs[6]: st.dataframe(df.tail(200).iloc[::-1],width="stretch",hide_index=True,height=450)

render_daily_footer()
