"""Read-only performance analysis for Strategy 1.

This page intentionally mirrors Strategy 2 analysis so S1 and S2 can be
compared using the same KPIs, tabs, chart families and risk views.
"""
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from strategy.contracts import strategy_metadata

TRADES = ROOT / "outputs" / "trades.csv"
STARTING_CAPITAL = 250000.0

st.set_page_config(page_title="NSE Catalyst | Strategy 1 Analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)
try:
    ensure_bot_running()
except Exception:
    pass


def read_trades():
    try:
        return pd.read_csv(TRADES) if TRADES.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def numeric(frame, columns):
    for c in columns:
        if c not in frame.columns:
            frame[c] = 0.0
        frame[c] = pd.to_numeric(frame[c], errors="coerce").fillna(0.0)
    return frame


def chart(fig, key, height=330):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=48, b=8),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


meta = strategy_metadata("STRATEGY_1")
df = read_trades()
if not df.empty and "strategy" in df.columns:
    df = df[df["strategy"].astype(str).str.upper().isin(["STRATEGY_1", "S1", "OPEN_RETURN"])].copy()

df = numeric(df, ["pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "gap_percent", "actual_risk", "risk_per_share", "mae", "mfe"])
if "status" in df.columns:
    df = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()

df = df.reset_index(drop=True)
if not df.empty:
    df["Result"] = df["pnl"].map(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    df["Trade #"] = range(1, len(df) + 1)
    df["Cumulative P&L"] = df["pnl"].cumsum()
    df["Peak"] = df["Cumulative P&L"].cummax()
    df["Drawdown"] = df["Cumulative P&L"] - df["Peak"]

count = len(df)
wins = int((df["pnl"] > 0).sum()) if count else 0
losses = int((df["pnl"] < 0).sum()) if count else 0
net = float(df["pnl"].sum()) if count else 0.0
gross_profit = float(df.loc[df["pnl"] > 0, "pnl"].sum()) if count else 0.0
gross_loss = abs(float(df.loc[df["pnl"] < 0, "pnl"].sum())) if count else 0.0
win_rate = wins / count * 100 if count else 0.0
profit_factor = gross_profit / gross_loss if gross_loss else 0.0
max_dd = abs(float(df["Drawdown"].min())) if count else 0.0

st.title("📊 Strategy 1 — Complete Analysis")
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
    if df.empty:
        st.info("No completed Strategy 1 paper trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.line(df, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "s1_cum")
        with b: chart(px.area(df, x="Trade #", y="Drawdown", title="Drawdown"), "s1_dd")
        a, b = st.columns(2)
        with a: chart(px.pie(df["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Outcome Mix"), "s1_mix")
        with b: chart(px.bar(df.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "s1_result")

with tabs[1]:
    if df.empty:
        st.info("No completed trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.histogram(df, x="pnl", nbins=14, title="P&L Distribution"), "s1_pnl_dist")
        with b:
            roll = df[["Trade #", "pnl"]].copy()
            roll["Rolling Avg"] = roll["pnl"].rolling(5, min_periods=1).mean()
            chart(px.line(roll, x="Trade #", y="Rolling Avg", markers=True, title="5-Trade Rolling Average"), "s1_rolling")

with tabs[2]:
    if df.empty:
        st.info("No setup results yet.")
    else:
        if "signal" in df.columns:
            side = df.groupby("signal", as_index=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), PnL=("pnl", "sum"))
            a, b = st.columns(2)
            with a: chart(px.bar(side, x="signal", y="Win_Rate", text="Trades", title="Win Rate by Side"), "s1_side_win")
            with b: chart(px.bar(side, x="signal", y="PnL", text="Trades", title="P&L by Side"), "s1_side_pnl")
        if "gap_percent" in df.columns:
            gap = df.copy()
            gap["Gap Band"] = pd.cut(gap["gap_percent"].abs(), bins=[-0.0001, 0.25, 0.75, float("inf")], labels=["<0.25%", "0.25–0.75%", ">0.75%"])
            st.dataframe(gap.groupby("Gap Band", observed=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index(), width="stretch", hide_index=True)

with tabs[3]:
    if df.empty or "symbol" not in df.columns:
        st.info("No stock-level results yet.")
    else:
        stock = df.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100)).sort_values("PnL", ascending=False)
        chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "s1_stocks", 360)
        st.dataframe(stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    if df.empty or "gap_percent" not in df.columns:
        st.info("No GAP results yet.")
    else:
        gap = df.copy(); gap["Gap Magnitude %"] = gap["gap_percent"].abs()
        a, b = st.columns(2)
        with a: chart(px.histogram(gap, x="Gap Magnitude %", nbins=12, title="Opening GAP Magnitude"), "s1_gap_dist")
        with b: chart(px.scatter(gap, x="Gap Magnitude %", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in gap.columns], title="GAP vs P&L"), "s1_gap_pnl")

with tabs[5]:
    if df.empty:
        st.info("No risk results yet.")
    else:
        a, b = st.columns(2)
        with a:
            chart(px.histogram(df, x="rr", nbins=12, title="Risk:Reward Distribution"), "s1_rr")
        with b:
            risk_col = "actual_risk" if "actual_risk" in df.columns and df["actual_risk"].abs().sum() else "risk_per_share"
            chart(px.scatter(df, x=risk_col, y="pnl", hover_data=[c for c in ["symbol", "signal", "quantity"] if c in df.columns], title="Actual Risk vs P&L" if risk_col == "actual_risk" else "Risk per Share vs P&L"), "s1_risk")
        if "actual_risk" in df.columns:
            band = df[["actual_risk", "pnl"]].copy()
            band["Risk Band"] = band["actual_risk"].apply(lambda x: "< ₹1,400" if x < 1400 else "₹1,400–₹1,500" if x <= 1500 else "> ₹1,500")
            summary = band.groupby("Risk Band", as_index=False).agg(Trades=("pnl", "size"), Net_PnL=("pnl", "sum"))
            chart(px.bar(summary, x="Risk Band", y="Trades", text="Trades", title="Actual Risk Band"), "s1_risk_band")

with tabs[6]:
    if df.empty or "entry_time" not in df.columns:
        st.info("No timing results yet.")
    else:
        dates = pd.to_datetime(df["entry_time"], errors="coerce")
        if dates.dt.tz is None: dates = dates.dt.tz_localize("Asia/Kolkata")
        else: dates = dates.dt.tz_convert("Asia/Kolkata")
        timing = pd.DataFrame({"Entry Minute": dates.dt.hour * 60 + dates.dt.minute, "P&L": df["pnl"], "RR": df["rr"]})
        a, b = st.columns(2)
        with a: chart(px.scatter(timing, x="Entry Minute", y="P&L", title="Entry Time vs P&L"), "s1_timing")
        with b: chart(px.scatter(timing, x="Entry Minute", y="RR", title="Entry Time vs Risk:Reward"), "s1_timing_rr")

with tabs[7]:
    if df.empty: st.info("No completed trades yet.")
    else: st.dataframe(df.tail(200).iloc[::-1], width="stretch", hide_index=True, height=450)

render_daily_footer()
