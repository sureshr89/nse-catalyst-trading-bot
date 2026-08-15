"""Page 3: concise read-only analysis for the current strategy."""
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
        return pd.read_csv(TRADES)
    except Exception:
        return pd.DataFrame()


def num(df, col):
    if col not in df.columns:
        df[col] = 0.0
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def cards(items):
    html = '<div class="analysis-kpi-grid">'
    for label, value in items:
        html += f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def chart(fig, key, height=300):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=42, b=8),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


df = read_trades()
if not df.empty:
    for column in ["pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "gap_percent"]:
        num(df, column)
    actual = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy() if "status" in df.columns else df.copy()
else:
    actual = pd.DataFrame()

if not actual.empty:
    actual["Result"] = actual["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    actual["Trade #"] = range(1, len(actual) + 1)
    actual["Cumulative P&L"] = actual["pnl"].cumsum()
    actual["Drawdown"] = actual["Cumulative P&L"] - actual["Cumulative P&L"].cummax()

count = len(actual)
wins = int((actual["pnl"] > 0).sum()) if count else 0
losses = int((actual["pnl"] < 0).sum()) if count else 0
net = float(actual["pnl"].sum()) if count else 0.0
winrate = wins / count * 100 if count else 0.0
loss_sum = abs(float(actual.loc[actual["pnl"] < 0, "pnl"].sum())) if count else 0.0
pf = float(actual.loc[actual["pnl"] > 0, "pnl"].sum()) / loss_sum if loss_sum else 0.0

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("Closed paper trades • PDH/PDL + Today's Open strategy")
cards([
    ("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"),
    ("Closed Trades", count),
    ("Net P&L", f"₹{net:,.2f}"),
    ("Current Equity", f"₹{STARTING_CAPITAL + net:,.2f}"),
    ("Win Rate", f"{winrate:.1f}%"),
    ("Wins", wins),
    ("Losses", losses),
    ("Profit Factor", f"{pf:.2f}"),
])

st.subheader("⚡ Current Strategy")
st.dataframe(
    pd.DataFrame([
        ("Universe", "NIFTY 500"),
        ("BUY", "Today's Open > PDH → price moves below PDH → return above Today's Open"),
        ("SELL", "Today's Open < PDL → price moves above PDL → return below Today's Open"),
        ("Market filter", "BUY ≥ +0.25% NIFTY 500 • SELL ≤ −0.25% NIFTY 500"),
        ("Entry window", "09:45–14:00 IST"),
    ], columns=["Rule", "Definition"]),
    use_container_width=True,
    hide_index=True,
)

tabs = st.tabs(["📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "⚖️ Risk / Reward", "📋 Trades"])

with tabs[0]:
    st.subheader("Performance Overview")
    a, b = st.columns(2)
    if actual.empty:
        with a:
            st.info("No completed paper trades yet.")
        with b:
            st.info("No drawdown data yet.")
    else:
        with a:
            chart(px.line(actual, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "cum")
        with b:
            chart(px.line(actual, x="Trade #", y="Drawdown", markers=True, title="Drawdown"), "dd")

    a, b = st.columns(2)
    if actual.empty:
        with a:
            st.info("No result data yet.")
        with b:
            st.info("No result data yet.")
    else:
        with a:
            chart(px.pie(actual["Result"].value_counts().rename_axis("Result").reset_index(name="Trades"), names="Result", values="Trades", title="Win / Loss / Flat"), "mix")
        with b:
            chart(px.bar(actual.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", title="P&L by Result"), "result_pnl")

with tabs[1]:
    st.subheader("P&L Analysis")
    if actual.empty:
        st.info("No completed paper trades yet.")
    else:
        a, b = st.columns(2)
        if "entry_time" in actual.columns:
            daily = actual.copy()
            daily["Date"] = pd.to_datetime(daily["entry_time"], errors="coerce").dt.strftime("%d %b")
            daily = daily.groupby("Date", as_index=False)["pnl"].sum()
            with a:
                chart(px.bar(daily, x="Date", y="pnl", title="Daily P&L"), "daily_pnl")
        else:
            with a:
                chart(px.bar(actual, x="Trade #", y="pnl", title="P&L per Trade"), "pnl_by_trade")
        with b:
            chart(px.histogram(actual, x="pnl", nbins=12, title="P&L Distribution"), "pnl_distribution")

with tabs[2]:
    st.subheader("Setup Performance")
    a, b = st.columns(2)
    if actual.empty:
        with a:
            st.info("No setup results yet.")
        with b:
            st.info("No setup results yet.")
    else:
        if "signal" in actual.columns:
            side = actual.groupby("signal")["pnl"].agg(Trades="size", PnL="sum").reset_index()
            with a:
                chart(px.bar(side, x="signal", y="PnL", text="Trades", title="BUY vs SELL P&L"), "setup_side")
        else:
            with a:
                st.info("No BUY/SELL data recorded yet.")
        if "setup_type" in actual.columns:
            setup = actual.groupby("setup_type")["pnl"].agg(Trades="size", PnL="sum").reset_index()
            with b:
                chart(px.bar(setup, x="setup_type", y="PnL", text="Trades", title="P&L by Setup Type"), "setup_type")
        else:
            with b:
                st.info("No setup-type data recorded yet.")

    if not actual.empty and "gap_percent" in actual.columns:
        gap = actual.copy()
        gap["Gap Band"] = pd.cut(
            gap["gap_percent"].abs(),
            bins=[-0.0001, 0.25, 0.75, float("inf")],
            labels=["<0.25%", "0.25–0.75%", ">0.75%"],
        )
        summary = gap.groupby("Gap Band", observed=False).agg(
            Trades=("pnl", "size"),
            Win_Rate=("pnl", lambda z: (z > 0).mean() * 100),
            Net_PnL=("pnl", "sum"),
        ).reset_index()
        st.dataframe(summary, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Stock Performance")
    if actual.empty or "symbol" not in actual.columns:
        st.info("No completed stock-level results yet.")
    else:
        stock = actual.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum")).sort_values("PnL", ascending=False)
        a, b = st.columns(2)
        with a:
            chart(px.bar(stock.head(15), x="symbol", y="PnL", text="Trades", title="Top Stocks"), "topstocks", 340)
        with b:
            chart(px.bar(stock.tail(15).sort_values("PnL"), x="symbol", y="PnL", text="Trades", title="Weakest Stocks"), "weakstocks", 340)
        st.dataframe(stock, use_container_width=True, hide_index=True, height=340)

with tabs[4]:
    st.subheader("Risk & Reward")
    if actual.empty:
        st.info("No completed risk data yet.")
    else:
        a, b = st.columns(2)
        with a:
            if "rr" in actual.columns:
                chart(px.histogram(actual, x="rr", nbins=12, title="Risk : Reward Distribution"), "rr")
            else:
                st.info("No R:R data recorded yet.")
        with b:
            if "risk_per_share" in actual.columns:
                chart(px.scatter(actual, x="risk_per_share", y="pnl", title="Risk per Share vs P&L"), "riskpnl")
            else:
                st.info("No risk-per-share data recorded yet.")

with tabs[5]:
    st.subheader("Closed Trades")
    if actual.empty:
        st.info("No completed paper trades yet.")
    else:
        columns = [c for c in ["entry_time", "exit_time", "symbol", "signal", "entry", "stop_loss", "target", "quantity", "pnl", "Result", "exit_reason"] if c in actual.columns]
        st.dataframe(actual[columns].iloc[::-1], use_container_width=True, hide_index=True, height=520)

st.caption("Read-only analysis • Paper trading only")
render_daily_footer()
