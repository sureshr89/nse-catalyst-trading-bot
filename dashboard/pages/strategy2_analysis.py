"""Read-only performance analysis for Strategy 2.

The layout intentionally mirrors Strategy 1 analysis: identical KPI family,
tab order, chart families and risk analysis, with S2-specific GAP/reversal
metrics inside those shared sections.
"""
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.strategy2_data import closed_trades, today_signals, STARTING_CAPITAL
from strategy.contracts import strategy_metadata

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def chart(fig, key, height=330):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=48, b=8),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


def numeric(df, columns):
    for c in columns:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


meta = strategy_metadata("STRATEGY_2")
closed = numeric(
    closed_trades().copy(),
    ["pnl", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_per_share", "rr", "gap_percent", "mae", "mfe"],
)
live = numeric(
    today_signals().copy(),
    ["entry", "stop_loss", "target", "risk_reward", "gap_percent", "priority_rank", "today_open", "today_high", "today_low", "nifty500_change_pct", "actual_risk", "quantity"],
)

if not closed.empty:
    closed = closed.reset_index(drop=True)
    closed["Trade #"] = range(1, len(closed) + 1)
    closed["Result"] = closed["pnl"].map(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    closed["Cumulative P&L"] = closed["pnl"].cumsum()
    closed["Peak"] = closed["Cumulative P&L"].cummax()
    closed["Drawdown"] = closed["Cumulative P&L"] - closed["Peak"]

if not live.empty:
    live["Gap Magnitude %"] = live["gap_percent"].abs()
    live["Risk / Share"] = (live["stop_loss"] - live["entry"]).abs()
    live["Reward / Share"] = (live["entry"] - live["target"]).abs()
    live["Actual Risk"] = pd.to_numeric(live.get("actual_risk", 0.0), errors="coerce").fillna(0.0)
    live["Risk Band"] = live["Actual Risk"].apply(lambda x: "< ₹1,400" if x < 1400 else "₹1,400–₹1,500" if x <= 1500 else "> ₹1,500")

count = len(closed)
wins = int((closed["pnl"] > 0).sum()) if count else 0
losses = int((closed["pnl"] < 0).sum()) if count else 0
net = float(closed["pnl"].sum()) if count else 0.0
gross_profit = float(closed.loc[closed["pnl"] > 0, "pnl"].sum()) if count else 0.0
gross_loss = abs(float(closed.loc[closed["pnl"] < 0, "pnl"].sum())) if count else 0.0
win_rate = wins / count * 100 if count else 0.0
profit_factor = gross_profit / gross_loss if gross_loss else 0.0
max_dd = abs(float(closed["Drawdown"].min())) if count else 0.0

st.title("📊 Strategy 2 — Complete Analysis")
st.caption(f"{meta['name']} • contract v{meta['version']} • isolated ₹2,50,000 paper capital • analysis only — no position changes")

html = '<div class="analysis-kpi-grid">'
for label, value in [
    ("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"),
    ("Closed Trades", count),
    ("Wins / Losses", f"{wins} / {losses}"),
    ("Net P&L", f"₹{net:,.2f}"),
    ("Equity", f"₹{STARTING_CAPITAL + net:,.2f}"),
    ("Win Rate", f"{win_rate:.1f}%"),
    ("Profit Factor", f"{profit_factor:.2f}"),
    ("Max Drawdown", f"₹{max_dd:,.2f}"),
]:
    html += f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
html += "</div>"
st.markdown(html, unsafe_allow_html=True)

st.subheader("⚡ Authoritative Strategy Rules")
rules = list(meta["rules"]) + [
    ("Risk", "₹1,400–₹1,500 intended actual risk • maximum 2 positions"),
    ("Entry window", "09:45–14:00 IST"),
    ("Monitoring", "Completed 1-minute strategy candles"),
    ("Square-off", "15:00 IST"),
]
st.dataframe(pd.DataFrame(rules, columns=["Rule", "Definition"]), width="stretch", hide_index=True)

tabs = st.tabs(["📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "📏 GAP", "⚖️ Risk / Reward", "⏱️ Timing", "📋 Trades"])

with tabs[0]:
    if closed.empty:
        st.info("No completed Strategy 2 paper trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.line(closed, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "s2_cum")
        with b: chart(px.area(closed, x="Trade #", y="Drawdown", title="Drawdown"), "s2_dd")
        a, b = st.columns(2)
        with a: chart(px.pie(closed["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Outcome Mix"), "s2_mix")
        with b: chart(px.bar(closed.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "s2_result")

with tabs[1]:
    if closed.empty:
        st.info("No completed trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.histogram(closed, x="pnl", nbins=14, title="P&L Distribution"), "s2_pnl_dist")
        with b:
            roll = closed[["Trade #", "pnl"]].copy()
            roll["Rolling Avg"] = roll["pnl"].rolling(5, min_periods=1).mean()
            chart(px.line(roll, x="Trade #", y="Rolling Avg", markers=True, title="5-Trade Rolling Average"), "s2_rolling")

with tabs[2]:
    if live.empty and closed.empty:
        st.info("No Strategy 2 setup results yet.")
    else:
        if not live.empty:
            st.subheader("📡 Today's S2 Decision Analysis")
            a, b = st.columns(2)
            with a:
                side = live["signal"].astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions") if "signal" in live.columns else pd.DataFrame(columns=["Signal", "Decisions"])
                if not side.empty: chart(px.bar(side, x="Signal", y="Decisions", text="Decisions", title="BUY vs SELL Decisions"), "s2_side_live")
            with b:
                stock = live.groupby("symbol", as_index=False).size().rename(columns={"size": "Decisions"}).sort_values("Decisions", ascending=False).head(20) if "symbol" in live.columns else pd.DataFrame()
                if not stock.empty: chart(px.bar(stock.sort_values("Decisions"), x="Decisions", y="symbol", orientation="h", text="Decisions", title="Decision Count by Stock"), "s2_stock_live")
            a, b = st.columns(2)
            with a:
                chart(px.scatter(live, x="Gap Magnitude %", y="risk_reward", hover_data=[c for c in ["symbol", "signal", "entry", "stop_loss", "target"] if c in live.columns], title="GAP Magnitude vs Risk:Reward"), "s2_gap_rr_live")
            with b:
                chart(px.histogram(live, x="risk_reward", nbins=14, title="Live Risk:Reward Distribution"), "s2_rr_live")
            st.dataframe(live.tail(200).iloc[::-1], width="stretch", hide_index=True, height=360)

        if not closed.empty and "signal" in closed.columns:
            side_closed = closed.groupby("signal", as_index=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), PnL=("pnl", "sum"))
            a, b = st.columns(2)
            with a: chart(px.bar(side_closed, x="signal", y="Win_Rate", text="Trades", title="Win Rate by Side"), "s2_side_win")
            with b: chart(px.bar(side_closed, x="signal", y="PnL", text="Trades", title="P&L by Side"), "s2_side_pnl")

with tabs[3]:
    if closed.empty or "symbol" not in closed.columns:
        st.info("No stock-level results yet.")
    else:
        stock = closed.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100)).sort_values("PnL", ascending=False)
        chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "s2_stocks", 360)
        st.dataframe(stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    source = closed if not closed.empty else live
    if source.empty or "gap_percent" not in source.columns:
        st.info("No GAP results yet.")
    else:
        gap = source.copy(); gap["Gap Magnitude %"] = gap["gap_percent"].abs()
        a, b = st.columns(2)
        with a: chart(px.histogram(gap, x="Gap Magnitude %", nbins=12, title="Opening GAP Magnitude"), "s2_gap_dist")
        with b:
            y = "pnl" if "pnl" in gap.columns else "risk_reward"
            title = "GAP vs P&L" if y == "pnl" else "GAP vs Risk:Reward"
            hover = [c for c in ["symbol", "signal"] if c in gap.columns]
            chart(px.scatter(gap, x="Gap Magnitude %", y=y, hover_data=hover, title=title), "s2_gap_relation")

with tabs[5]:
    source = closed if not closed.empty else live
    if source.empty:
        st.info("No risk results yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.histogram(source, x="rr" if "rr" in source.columns else "risk_reward", nbins=12, title="Risk:Reward Distribution"), "s2_rr")
        with b:
            risk_col = "actual_risk" if "actual_risk" in source.columns and source["actual_risk"].abs().sum() else "risk_per_share"
            chart(px.scatter(source, x=risk_col, y="pnl" if "pnl" in source.columns else "risk_reward", hover_data=[c for c in ["symbol", "signal", "quantity"] if c in source.columns], title="Actual Risk vs P&L" if "pnl" in source.columns and risk_col == "actual_risk" else "Risk vs Result"), "s2_risk")
        if "actual_risk" in source.columns and source["actual_risk"].abs().sum():
            band = source[["actual_risk"]].copy()
            band["Risk Band"] = band["actual_risk"].apply(lambda x: "< ₹1,400" if x < 1400 else "₹1,400–₹1,500" if x <= 1500 else "> ₹1,500")
            summary = band.groupby("Risk Band", as_index=False).size().rename(columns={"size": "Trades"})
            chart(px.bar(summary, x="Risk Band", y="Trades", text="Trades", title="Actual Risk Band"), "s2_risk_band")

with tabs[6]:
    source = closed if not closed.empty else live
    time_col = "entry_time" if "entry_time" in source.columns else "timestamp" if "timestamp" in source.columns else None
    if source.empty or not time_col:
        st.info("No timing results yet.")
    else:
        dates = pd.to_datetime(source[time_col], errors="coerce")
        dates = dates.dt.tz_localize("Asia/Kolkata") if dates.dt.tz is None else dates.dt.tz_convert("Asia/Kolkata")
        timing = pd.DataFrame({"Entry Minute": dates.dt.hour * 60 + dates.dt.minute})
        if "pnl" in source.columns: timing["P&L"] = source["pnl"].values
        if "rr" in source.columns: timing["RR"] = source["rr"].values
        a, b = st.columns(2)
        with a:
            if "P&L" in timing: chart(px.scatter(timing, x="Entry Minute", y="P&L", title="Entry Time vs P&L"), "s2_timing")
        with b:
            if "RR" in timing: chart(px.scatter(timing, x="Entry Minute", y="RR", title="Entry Time vs Risk:Reward"), "s2_timing_rr")

with tabs[7]:
    if closed.empty: st.info("No completed Strategy 2 trades yet.")
    else: st.dataframe(closed.tail(200).iloc[::-1], width="stretch", hide_index=True, height=450)

render_daily_footer()
