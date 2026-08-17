"""Read-only performance analysis for the NIFTY 500 gap/open-return strategy."""
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

TRADES = ROOT / "outputs" / "trades.csv"
STARTING_CAPITAL = 250000.0

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
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


def clean(frame):
    if frame.empty:
        return frame
    blocked = [c for c in frame.columns if "atr" in str(c).lower() or "average_true_range" in str(c).lower()]
    return frame.drop(columns=blocked, errors="ignore")


def number(frame, column):
    if column not in frame.columns:
        frame[column] = 0.0
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def chart(fig, key, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=48, b=8), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


df = clean(read_trades())
if not df.empty:
    for col in ["pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "gap_percent", "actual_risk", "risk_per_share", "mae", "mfe"]:
        number(df, col)
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

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("Closed-trade analysis • PDH/PDL + Today's Open Return • Highest GAP priority")

html = '<div class="analysis-kpi-grid">'
for label, value in [("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"), ("Closed Trades", count), ("Wins / Losses", f"{wins} / {losses}"), ("Net P&L", f"₹{net:,.2f}"), ("Current Equity", f"₹{STARTING_CAPITAL + net:,.2f}"), ("Win Rate", f"{win_rate:.1f}%"), ("Profit Factor", f"{profit_factor:.2f}"), ("Max Drawdown", f"₹{max_dd:,.2f}")]:
    html += f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
html += "</div>"
st.markdown(html, unsafe_allow_html=True)

st.subheader("⚡ Strategy Rules Being Analysed")
st.dataframe(pd.DataFrame([
    ("Universe", "NIFTY 500"),
    ("BUY", "NIFTY 500 ≥ +0.25% • Open > PDH • completed 1m return to Today's Open"),
    ("SELL", "NIFTY 500 ≤ −0.25% • Open < PDL • completed 1m return to Today's Open"),
    ("Ranking", "Largest qualifying absolute GAP % first"),
    ("Entry window", "09:45–14:00 IST"),
    ("Stop loss", "BUY = PDH • SELL = PDL"),
    ("Target", "1.25R"),
    ("Risk", "₹1,400–₹1,500 intended risk • maximum 2 positions"),
    ("Monitoring", "30-second control cycle with completed 1-minute strategy candles"),
    ("Square-off", "15:00 IST"),
], columns=["Rule", "Definition"]), width="stretch", hide_index=True)

tabs = st.tabs(["📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "📏 GAP", "⚖️ Risk / Reward", "⏱️ Timing", "📋 Trades"])

with tabs[0]:
    if df.empty:
        st.info("No completed paper trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.line(df, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "cum")
        with b: chart(px.area(df, x="Trade #", y="Drawdown", title="Drawdown"), "dd")
        a, b = st.columns(2)
        with a: chart(px.pie(df["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Outcome Mix"), "mix")
        with b: chart(px.bar(df.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "result")

with tabs[1]:
    if df.empty:
        st.info("No completed trades yet.")
    else:
        a, b = st.columns(2)
        with a: chart(px.histogram(df, x="pnl", nbins=14, title="P&L Distribution"), "pnl_dist")
        with b:
            roll = df[["Trade #", "pnl"]].copy()
            roll["Rolling Avg"] = roll["pnl"].rolling(5, min_periods=1).mean()
            chart(px.line(roll, x="Trade #", y="Rolling Avg", markers=True, title="5-Trade Rolling Average"), "rolling")

with tabs[2]:
    if df.empty:
        st.info("No setup results yet.")
    else:
        if "signal" in df.columns:
            side = df.groupby("signal", as_index=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), PnL=("pnl", "sum"))
            chart(px.bar(side, x="signal", y="Win_Rate", text="Trades", title="Win Rate by Side"), "side_win")
        if "gap_percent" in df.columns:
            gap = df.copy()
            gap["Gap Band"] = pd.cut(gap["gap_percent"].abs(), bins=[-0.0001, 0.25, 0.75, float("inf")], labels=["<0.25%", "0.25–0.75%", ">0.75%"])
            st.dataframe(gap.groupby("Gap Band", observed=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index(), width="stretch", hide_index=True)

with tabs[3]:
    if df.empty or "symbol" not in df.columns:
        st.info("No stock-level results yet.")
    else:
        stock = df.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100)).sort_values("PnL", ascending=False)
        chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "stocks", 360)
        st.dataframe(stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    if df.empty or "gap_percent" not in df.columns:
        st.info("No GAP results yet.")
    else:
        gap = df.copy(); gap["Gap Magnitude %"] = gap["gap_percent"].abs()
        a, b = st.columns(2)
        with a: chart(px.histogram(gap, x="Gap Magnitude %", nbins=12, title="Opening GAP Magnitude"), "gap_dist")
        with b: chart(px.scatter(gap, x="Gap Magnitude %", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in gap.columns], title="GAP vs P&L"), "gap_pnl")

with tabs[5]:
    if df.empty:
        st.info("No risk results yet.")
    else:
        a, b = st.columns(2)
        with a:
            if "rr" in df.columns: chart(px.histogram(df, x="rr", nbins=12, title="Risk:Reward"), "rr")
        with b:
            if "risk_per_share" in df.columns: chart(px.scatter(df, x="risk_per_share", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in df.columns], title="Risk per Share vs P&L"), "risk")

with tabs[6]:
    if df.empty or "entry_time" not in df.columns:
        st.info("No timing results yet.")
    else:
        dates = pd.to_datetime(df["entry_time"], errors="coerce")
        if dates.dt.tz is None: dates = dates.dt.tz_localize("Asia/Kolkata")
        else: dates = dates.dt.tz_convert("Asia/Kolkata")
        timing = pd.DataFrame({"Entry Minute": dates.dt.hour * 60 + dates.dt.minute, "P&L": df["pnl"]})
        chart(px.scatter(timing, x="Entry Minute", y="P&L", title="Entry Time vs P&L"), "timing")

with tabs[7]:
    if df.empty: st.info("No completed trades yet.")
    else: st.dataframe(df.tail(200).iloc[::-1], width="stretch", hide_index=True, height=450)

render_daily_footer()
