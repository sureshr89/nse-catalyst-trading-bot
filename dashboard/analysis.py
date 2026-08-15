"""Read-only performance analysis for the NIFTY 500 paper strategy."""
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dashboard.style import load_css

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "outputs" / "trades.csv"
STARTING_CAPITAL = 250000.0
IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)


def read_trades():
    try:
        return pd.read_csv(TRADES)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def prepare(df):
    if df.empty:
        return df
    df = df.copy()
    for col in ["entry", "stop_loss", "target", "quantity", "risk_per_share", "actual_risk", "position_value", "pnl", "rr"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
    return df


def empty_chart(title, key, height=300):
    fig = go.Figure()
    fig.update_layout(height=height, title=title, margin=dict(l=8, r=8, t=45, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(visible=False), yaxis=dict(visible=False))
    fig.add_annotation(text="No completed paper-trade data yet", x=.5, y=.5, xref="paper", yref="paper", showarrow=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


def chart(fig, key, height=300):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=45, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", size=12))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


def grouped(df, column, title, key):
    if df.empty or column not in df.columns:
        empty_chart(title, key)
        return
    g = df.groupby(column, dropna=False)["pnl"].agg(Trades="size", Net_PnL="sum").reset_index()
    chart(px.bar(g, x=column, y="Net_PnL", text="Trades", title=title), key)


trades = prepare(read_trades())
count = len(trades)
wins = int((trades["pnl"] > 0).sum()) if not trades.empty else 0
losses = int((trades["pnl"] < 0).sum()) if not trades.empty else 0
net_pnl = float(trades["pnl"].sum()) if not trades.empty else 0.0
win_rate = wins / count * 100 if count else 0.0
loss_sum = abs(float(trades.loc[trades["pnl"] < 0, "pnl"].sum())) if not trades.empty else 0.0
profit_factor = float(trades.loc[trades["pnl"] > 0, "pnl"].sum()) / loss_sum if loss_sum else 0.0

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("Closed paper trades • PDH/PDL + Today's Open strategy • No live orders")

kpis = [("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"), ("Closed Trades", count), ("Net P&L", f"₹{net_pnl:,.2f}"), ("Current Equity", f"₹{STARTING_CAPITAL + net_pnl:,.2f}"), ("Win Rate", f"{win_rate:.1f}%"), ("Wins", wins), ("Losses", losses), ("Profit Factor", f"{profit_factor:.2f}")]
st.markdown('<div class="analysis-kpi-grid">' + "".join(f'<div class="analysis-kpi"><span>{a}</span><strong>{b}</strong></div>' for a, b in kpis) + '</div>', unsafe_allow_html=True)

tabs = st.tabs(["📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "🌐 Alignment", "⚖️ Risk / Reward", "📋 Trades"])

with tabs[0]:
    st.subheader("Performance Overview")
    if trades.empty:
        a, b = st.columns(2)
        with a: empty_chart("Cumulative P&L", "ov_cum")
        with b: empty_chart("Drawdown", "ov_dd")
    else:
        x = trades.copy()
        x["Trade #"] = range(1, len(x) + 1)
        x["Cumulative P&L"] = x["pnl"].cumsum()
        x["Drawdown"] = x["Cumulative P&L"] - x["Cumulative P&L"].cummax()
        a, b = st.columns(2)
        with a: chart(px.line(x, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "ov_cum")
        with b: chart(px.line(x, x="Trade #", y="Drawdown", markers=True, title="Drawdown"), "ov_dd")
        a, b = st.columns(2)
        with a: chart(px.pie(x["pnl"].apply(lambda v: "WIN" if v > 0 else "LOSS" if v < 0 else "FLAT").value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Result Mix"), "ov_mix")
        with b: chart(px.bar(x, x="Trade #", y="pnl", title="P&L per Trade"), "ov_trade")

with tabs[1]:
    st.subheader("P&L Analysis")
    if trades.empty:
        empty_chart("P&L per Trade", "pnl_trade")
    else:
        a, b = st.columns(2)
        with a: chart(px.bar(trades.reset_index(), x="index", y="pnl", title="P&L per Trade"), "pnl_trade")
        if "exit_time" in trades.columns:
            dates = pd.to_datetime(trades["exit_time"], errors="coerce").dt.strftime("%d %b")
            daily = trades.assign(Date=dates).groupby("Date", sort=False, as_index=False)["pnl"].sum()
            with b: chart(px.bar(daily, x="Date", y="pnl", title="Daily P&L"), "pnl_day")
        else:
            with b: empty_chart("Daily P&L", "pnl_day")

with tabs[2]:
    st.subheader("Strategy Setup Performance")
    a, b = st.columns(2)
    with a: grouped(trades, "signal", "P&L by BUY / SELL", "setup_side")
    with b: grouped(trades, "gap_type", "P&L by Gap Type", "setup_gap")
    a, b = st.columns(2)
    with a: grouped(trades, "exit_reason", "P&L by Exit Reason", "setup_exit")
    with b: grouped(trades, "setup_type", "P&L by Setup Type", "setup_type")

with tabs[3]:
    st.subheader("Stock Performance")
    if trades.empty or "symbol" not in trades.columns:
        empty_chart("Stock Performance", "stock_all", 360)
    else:
        by_stock = trades.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), Net_PnL=("pnl", "sum")).sort_values("Net_PnL", ascending=False)
        chart(px.bar(by_stock.head(20), x="symbol", y="Net_PnL", text="Trades", title="Top Stocks by P&L"), "stock_top", 360)
        st.dataframe(by_stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    st.subheader("NIFTY 500 + Industry/Sector + Stock Alignment")
    a, b = st.columns(2)
    with a: grouped(trades, "market_direction", "P&L by NIFTY 500 Direction", "market_dir")
    with b: grouped(trades, "sector_direction", "P&L by Industry/Sector Direction", "sector_dir")
    grouped(trades, "stock_direction", "P&L by Stock Direction", "stock_dir")
    if not trades.empty:
        cols = [c for c in ["symbol", "signal", "market_direction", "sector_direction", "stock_direction", "nifty500_change_pct", "entry_time", "pnl"] if c in trades.columns]
        if cols:
            st.dataframe(trades[cols].iloc[::-1].head(100), width="stretch", hide_index=True)

with tabs[5]:
    st.subheader("Risk & Reward")
    a, b = st.columns(2)
    with a:
        chart(px.histogram(trades, x="rr", nbins=12, title="Risk : Reward Distribution"), "risk_rr") if not trades.empty else empty_chart("Risk : Reward Distribution", "risk_rr")
    with b:
        chart(px.scatter(trades, x="risk_per_share", y="pnl", title="Risk per Share vs P&L"), "risk_pnl") if not trades.empty else empty_chart("Risk per Share vs P&L", "risk_pnl")
    a, b = st.columns(2)
    with a:
        chart(px.histogram(trades, x="actual_risk", nbins=12, title="Actual Risk Distribution"), "risk_actual") if not trades.empty else empty_chart("Actual Risk Distribution", "risk_actual")
    with b:
        chart(px.histogram(trades, x="target", nbins=12, title="Target Distribution"), "risk_target") if not trades.empty else empty_chart("Target Distribution", "risk_target")

with tabs[6]:
    st.subheader("Closed Trades")
    if trades.empty:
        st.info("No completed paper trades yet.")
    else:
        preferred = ["symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "market_direction", "sector_direction", "stock_direction", "pnl", "exit_reason"]
        cols = [c for c in preferred if c in trades.columns]
        st.dataframe(trades[cols].iloc[::-1], width="stretch", hide_index=True, height=500)
