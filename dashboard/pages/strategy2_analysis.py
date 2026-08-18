from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.strategy2_data import closed_trades, today_signals, STARTING_CAPITAL
from strategy.contracts import strategy_metadata

st.set_page_config(
    page_title="NSE Catalyst | Strategy 2 Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
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
closed = closed_trades()
live = today_signals()

closed = numeric(
    closed.copy(),
    [
        "pnl", "entry", "stop_loss", "target", "quantity", "actual_risk",
        "risk_per_share", "rr", "gap_percent", "mae", "mfe",
    ],
)

if not closed.empty:
    closed = closed.reset_index(drop=True)
    closed["Trade #"] = range(1, len(closed) + 1)
    closed["Result"] = closed["pnl"].map(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    closed["Cumulative P&L"] = closed["pnl"].cumsum()
    closed["Peak"] = closed["Cumulative P&L"].cummax()
    closed["Drawdown"] = closed["Cumulative P&L"] - closed["Peak"]

live = numeric(
    live.copy(),
    [
        "entry", "stop_loss", "target", "risk_reward", "gap_percent",
        "priority_rank", "today_open", "today_high", "today_low",
        "nifty500_change_pct",
    ],
)

if not live.empty:
    live["Gap Magnitude %"] = live["gap_percent"].abs()
    live["Risk / Share"] = (live["stop_loss"] - live["entry"]).abs()
    live["Reward / Share"] = (live["entry"] - live["target"]).abs()
    time_col = "entry_time" if "entry_time" in live.columns else "timestamp" if "timestamp" in live.columns else None
    if time_col:
        live["Trigger Time"] = pd.to_datetime(live[time_col], errors="coerce")
        if getattr(live["Trigger Time"].dt, "tz", None) is None:
            live["Trigger Time"] = live["Trigger Time"].dt.tz_localize("Asia/Kolkata")
        else:
            live["Trigger Time"] = live["Trigger Time"].dt.tz_convert("Asia/Kolkata")
        live["Trigger Minute"] = live["Trigger Time"].dt.hour * 60 + live["Trigger Time"].dt.minute
    else:
        live["Trigger Minute"] = 0

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
    ("Today's Decisions", len(live)),
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

st.subheader("📡 Live Strategy 2 Decision Analysis")
st.caption("These charts read the existing Strategy 2 decision/signal log only. They do not create, modify, close, or reopen positions.")

if live.empty:
    st.info("No Strategy 2 decisions recorded for today yet. Live charts will populate automatically when the scanner produces decisions.")
else:
    # 1. Decision volume by stock
    a, b = st.columns(2)
    with a:
        by_stock = (
            live.groupby("symbol", as_index=False)
            .size()
            .rename(columns={"size": "Decisions"})
            .sort_values("Decisions", ascending=False)
            .head(20)
        )
        chart(
            px.bar(
                by_stock.sort_values("Decisions"),
                x="Decisions",
                y="symbol",
                orientation="h",
                text="Decisions",
                title="Decision Count by Stock",
            ),
            "s2_live_stock_count",
        )
    with b:
        side = live["signal"].astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions") if "signal" in live.columns else pd.DataFrame(columns=["Signal", "Decisions"])
        if side.empty:
            st.info("No BUY/SELL classification available yet.")
        else:
            chart(px.bar(side, x="Signal", y="Decisions", text="Decisions", title="BUY vs SELL Decisions"), "s2_live_side")

    # 2. Gap and RR quality
    a, b = st.columns(2)
    with a:
        chart(
            px.scatter(
                live,
                x="Gap Magnitude %",
                y="risk_reward",
                hover_data=[c for c in ["symbol", "signal", "entry", "stop_loss", "target", "priority_rank"] if c in live.columns],
                title="GAP Magnitude vs Risk:Reward",
            ),
            "s2_live_gap_rr",
        )
    with b:
        chart(
            px.histogram(live, x="risk_reward", nbins=14, title="Live Risk:Reward Distribution"),
            "s2_live_rr_dist",
        )

    # 3. Entry / SL / target relationship
    levels = live.copy()
    if "symbol" in levels.columns:
        levels = levels.reset_index(drop=True)
        levels["Decision"] = levels["symbol"].astype(str) + " • " + levels.index.astype(str)
    else:
        levels["Decision"] = levels.index.astype(str)
    if len(levels) > 30:
        levels = levels.head(30)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=levels["Decision"], y=levels["entry"], mode="markers", name="Entry"))
    fig.add_trace(go.Scatter(x=levels["Decision"], y=levels["stop_loss"], mode="markers", name="Stop Loss"))
    fig.add_trace(go.Scatter(x=levels["Decision"], y=levels["target"], mode="markers", name="Target"))
    fig.update_layout(title="Entry vs Stop Loss vs Target", xaxis_title="Decision", yaxis_title="Price")
    chart(fig, "s2_live_levels", height=390)

    # 4. Trigger timing and priority
    a, b = st.columns(2)
    with a:
        if live["Trigger Minute"].ne(0).any():
            timing = live[live["Trigger Minute"] > 0].copy()
            chart(
                px.scatter(
                    timing,
                    x="Trigger Minute",
                    y="risk_reward",
                    hover_data=[c for c in ["symbol", "signal", "entry", "gap_percent"] if c in timing.columns],
                    title="Trigger Time vs Risk:Reward",
                ),
                "s2_live_timing",
            )
        else:
            st.info("Trigger timestamps are not available yet.")
    with b:
        priority = live.groupby("priority_rank", as_index=False).size().rename(columns={"size": "Decisions"})
        chart(px.bar(priority, x="priority_rank", y="Decisions", text="Decisions", title="Priority Rank Distribution"), "s2_live_priority")

    # 5. Gap distribution
    a, b = st.columns(2)
    with a:
        chart(px.histogram(live, x="Gap Magnitude %", nbins=14, title="Opening GAP Magnitude Distribution"), "s2_live_gap_dist")
    with b:
        if "nifty500_change_pct" in live.columns:
            chart(
                px.scatter(
                    live,
                    x="nifty500_change_pct",
                    y="risk_reward",
                    hover_data=[c for c in ["symbol", "signal", "gap_percent"] if c in live.columns],
                    title="NIFTY 500 Change vs Risk:Reward",
                ),
                "s2_live_nifty_rr",
            )

    st.subheader("📋 Live Decision Data")
    st.dataframe(live.tail(300).iloc[::-1], width="stretch", hide_index=True, height=430)

st.subheader("⚡ Authoritative Rules")
st.dataframe(pd.DataFrame(meta["rules"], columns=["Rule", "Definition"]), width="stretch", hide_index=True)

if closed.empty:
    st.info("No completed Strategy 2 trades yet. Closed-trade performance charts will appear automatically after the first completed trade.")
else:
    st.subheader("📈 Closed-Trade Performance")
    tabs = st.tabs(["📌 Overview", "💰 P&L", "🏆 Stocks", "📏 GAP", "⚖️ Risk", "⏱️ Timing", "📋 Trades"])
    with tabs[0]:
        a, b = st.columns(2)
        with a:
            chart(px.line(closed, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "s2_cum")
        with b:
            chart(px.area(closed, x="Trade #", y="Drawdown", title="Drawdown"), "s2_dd")
        a, b = st.columns(2)
        with a:
            chart(px.pie(closed["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Outcome Mix"), "s2_mix")
        with b:
            chart(px.bar(closed.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "s2_result")
    with tabs[1]:
        a, b = st.columns(2)
        with a:
            chart(px.histogram(closed, x="pnl", nbins=14, title="P&L Distribution"), "s2_dist")
        with b:
            roll = closed[["Trade #", "pnl"]].copy()
            roll["Rolling Avg"] = roll["pnl"].rolling(5, min_periods=1).mean()
            chart(px.line(roll, x="Trade #", y="Rolling Avg", markers=True, title="5-Trade Rolling Average"), "s2_roll")
    with tabs[2]:
        if "symbol" not in closed.columns:
            st.info("No stock-level results yet.")
        else:
            stock = closed.groupby("symbol", as_index=False).agg(
                Trades=("symbol", "size"),
                PnL=("pnl", "sum"),
                Win_Rate=("pnl", lambda x: (x > 0).mean() * 100),
            ).sort_values("PnL", ascending=False)
            chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "s2_stocks")
            st.dataframe(stock, width="stretch", hide_index=True)
    with tabs[3]:
        gap = closed.copy()
        gap["Gap Magnitude %"] = gap["gap_percent"].abs()
        a, b = st.columns(2)
        with a:
            chart(px.histogram(gap, x="Gap Magnitude %", nbins=12, title="Opening GAP Magnitude"), "s2_gap_dist")
        with b:
            chart(px.scatter(gap, x="Gap Magnitude %", y="pnl", hover_data=["symbol", "signal"], title="GAP vs P&L"), "s2_gap_pnl")
    with tabs[4]:
        a, b = st.columns(2)
        with a:
            chart(px.histogram(closed, x="rr", nbins=12, title="Recorded Risk:Reward"), "s2_rr")
        with b:
            chart(px.scatter(closed, x="risk_per_share", y="pnl", hover_data=["symbol", "signal"], title="Risk per Share vs P&L"), "s2_risk")
    with tabs[5]:
        if "entry_time" not in closed.columns:
            st.info("No timing results yet.")
        else:
            dates = pd.to_datetime(closed["entry_time"], errors="coerce")
            dates = dates.dt.tz_localize("Asia/Kolkata") if getattr(dates.dt, "tz", None) is None else dates.dt.tz_convert("Asia/Kolkata")
            timing = pd.DataFrame({"Entry Minute": dates.dt.hour * 60 + dates.dt.minute, "P&L": closed["pnl"]})
            chart(px.scatter(timing, x="Entry Minute", y="P&L", title="Entry Time vs P&L"), "s2_timing")
    with tabs[6]:
        st.dataframe(closed.tail(200).iloc[::-1], width="stretch", hide_index=True, height=450)

render_daily_footer()
