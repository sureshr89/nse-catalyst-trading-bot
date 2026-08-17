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
NEWS = ROOT / "outputs" / "MASTER_NEWS_ANALYSIS.csv"
STARTING_CAPITAL = 250000.0

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)
try:
    ensure_bot_running()
except Exception:
    pass


def read_csv(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def clean_strategy_columns(frame):
    """Remove any legacy volatility columns from historical files before display."""
    if frame.empty:
        return frame
    blocked = [c for c in frame.columns if "atr" in str(c).lower() or "average_true_range" in str(c).lower()]
    return frame.drop(columns=blocked, errors="ignore")


def num(frame, column):
    if column not in frame.columns:
        frame[column] = 0.0
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def chart(fig, key, height=320):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=48, b=8),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def safe_date(series):
    values = pd.to_datetime(series, errors="coerce")
    if getattr(values.dt, "tz", None) is not None:
        values = values.dt.tz_convert("Asia/Kolkata")
    return values


df = clean_strategy_columns(read_csv(TRADES))
if not df.empty:
    for column in ["pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "gap_percent", "actual_risk", "risk_per_share", "mae", "mfe"]:
        num(df, column)
    actual = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy() if "status" in df.columns else df.copy()
else:
    actual = pd.DataFrame()

if not actual.empty:
    actual = actual.reset_index(drop=True)
    actual["Result"] = actual["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    actual["Trade #"] = range(1, len(actual) + 1)
    actual["Cumulative P&L"] = actual["pnl"].cumsum()
    actual["Peak Equity P&L"] = actual["Cumulative P&L"].cummax()
    actual["Drawdown"] = actual["Cumulative P&L"] - actual["Peak Equity P&L"]
    if "entry_time" in actual.columns:
        actual["Entry DT"] = safe_date(actual["entry_time"])
    if "exit_time" in actual.columns:
        actual["Exit DT"] = safe_date(actual["exit_time"])
    if "Entry DT" in actual.columns and "Exit DT" in actual.columns:
        actual["Hold Minutes"] = (actual["Exit DT"] - actual["Entry DT"]).dt.total_seconds() / 60.0

count = len(actual)
wins = int((actual["pnl"] > 0).sum()) if count else 0
losses = int((actual["pnl"] < 0).sum()) if count else 0
net = float(actual["pnl"].sum()) if count else 0.0
winrate = wins / count * 100 if count else 0.0
loss_sum = abs(float(actual.loc[actual["pnl"] < 0, "pnl"].sum())) if count else 0.0
gross_profit = float(actual.loc[actual["pnl"] > 0, "pnl"].sum()) if count else 0.0
profit_factor = gross_profit / loss_sum if loss_sum else 0.0
max_dd = abs(float(actual["Drawdown"].min())) if count else 0.0
avg_trade = net / count if count else 0.0

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("Closed-trade analysis • PDH/PDL + Today's Open Return • GAP-first priority")

html = '<div class="analysis-kpi-grid">'
for label, value in [
    ("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"),
    ("Closed Trades", count),
    ("Net P&L", f"₹{net:,.2f}"),
    ("Current Equity", f"₹{STARTING_CAPITAL + net:,.2f}"),
    ("Win Rate", f"{winrate:.1f}%"),
    ("Profit Factor", f"{profit_factor:.2f}"),
    ("Average Trade", f"₹{avg_trade:,.2f}"),
    ("Max Drawdown", f"₹{max_dd:,.2f}"),
]:
    html += f'<div class="analysis-kpi"><span>{label}</span><strong>{value}</strong></div>'
html += "</div>"
st.markdown(html, unsafe_allow_html=True)

st.subheader("⚡ Strategy Rules Being Analysed")
st.dataframe(
    pd.DataFrame([
        ("Universe", "NIFTY 500"),
        ("BUY setup", "Today's Open > PDH → completed 1m close below PDH → completed 1m close back to Today's Open"),
        ("SELL setup", "Today's Open < PDL → completed 1m close above PDL → completed 1m close back to Today's Open"),
        ("Market filter", "BUY ≥ +0.25% NIFTY 500 • SELL ≤ −0.25% NIFTY 500"),
        ("Entry window", "09:45–14:00 IST"),
        ("Ranking", "Largest qualifying absolute GAP % first"),
        ("Risk", "SL at PDH/PDL • target at 1.25R • ₹1,400–₹1,500 intended risk"),
        ("News gate", "BUY requires POSITIVE news • SELL requires NEGATIVE news"),
    ], columns=["Rule", "Definition"]),
    width="stretch",
    hide_index=True,
)

tabs = st.tabs(["📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "📏 GAP", "⚖️ Risk / Reward", "⏱️ Timing", "📰 News", "📋 Trades"])

with tabs[0]:
    st.subheader("Performance Overview")
    if actual.empty:
        st.info("No completed paper trades yet. Charts will populate automatically after closed trades are recorded.")
    else:
        a, b = st.columns(2)
        with a:
            chart(px.line(actual, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "cum")
        with b:
            chart(px.area(actual, x="Trade #", y="Drawdown", title="Drawdown Curve"), "dd")
        a, b = st.columns(2)
        with a:
            outcomes = actual["Result"].value_counts().rename_axis("Result").reset_index(name="Trades")
            chart(px.pie(outcomes, names="Result", values="Trades", title="Trade Outcome Mix"), "mix")
        with b:
            result_pnl = actual.groupby("Result", as_index=False)["pnl"].sum()
            chart(px.bar(result_pnl, x="Result", y="pnl", text="pnl", title="P&L Contribution by Outcome"), "result_pnl")

with tabs[1]:
    st.subheader("💰 Detailed P&L")
    if actual.empty:
        st.info("No completed paper trades yet.")
    else:
        a, b = st.columns(2)
        if "Entry DT" in actual.columns and actual["Entry DT"].notna().any():
            daily = actual.dropna(subset=["Entry DT"]).copy()
            daily["Date"] = daily["Entry DT"].dt.strftime("%d %b")
            daily = daily.groupby("Date", as_index=False)["pnl"].sum()
            with a:
                chart(px.bar(daily, x="Date", y="pnl", text="pnl", title="Daily P&L"), "daily_pnl")
        with b:
            chart(px.histogram(actual, x="pnl", nbins=14, title="P&L Distribution"), "pnl_distribution")
        a, b = st.columns(2)
        with a:
            rolling = actual[["Trade #", "pnl"]].copy()
            rolling["Rolling Avg"] = rolling["pnl"].rolling(5, min_periods=1).mean()
            chart(px.line(rolling, x="Trade #", y="Rolling Avg", markers=True, title="5-Trade Rolling Average P&L"), "rolling_pnl")
        with b:
            if "signal" in actual.columns:
                side = actual.groupby("signal", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
                chart(px.bar(side, x="signal", y="PnL", text="Trades", title="BUY vs SELL Total P&L"), "side_pnl")

with tabs[2]:
    st.subheader("🎯 Setup Performance")
    if actual.empty:
        st.info("No setup results yet.")
    else:
        a, b = st.columns(2)
        if "signal" in actual.columns:
            side = actual.groupby("signal", as_index=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda z: (z > 0).mean() * 100), PnL=("pnl", "sum"))
            with a:
                chart(px.bar(side, x="signal", y="Win_Rate", text="Trades", title="Win Rate by Side"), "side_winrate")
        if "setup_type" in actual.columns:
            setup = actual.groupby("setup_type", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
            with b:
                chart(px.bar(setup, x="setup_type", y="PnL", text="Trades", title="P&L by Setup Type"), "setup_type_pnl")
        if "gap_percent" in actual.columns:
            gap = actual.copy()
            gap["Gap Band"] = pd.cut(gap["gap_percent"].abs(), bins=[-0.0001, 0.25, 0.75, float("inf")], labels=["<0.25%", "0.25–0.75%", ">0.75%"])
            summary = gap.groupby("Gap Band", observed=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda z: (z > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index()
            st.dataframe(summary, width="stretch", hide_index=True)

with tabs[3]:
    st.subheader("🏆 Stock-Level Performance")
    if actual.empty or "symbol" not in actual.columns:
        st.info("No completed stock-level results yet.")
    else:
        stock = actual.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum"), Win_Rate=("pnl", lambda z: (z > 0).mean() * 100)).sort_values("PnL", ascending=False)
        a, b = st.columns(2)
        with a:
            chart(px.bar(stock.head(15), x="symbol", y="PnL", text="Trades", title="Top 15 Stocks by P&L"), "topstocks", 360)
        with b:
            chart(px.bar(stock.tail(15).sort_values("PnL"), x="symbol", y="PnL", text="Trades", title="Bottom 15 Stocks by P&L"), "weakstocks", 360)
        chart(px.bar(stock.sort_values("Win_Rate", ascending=False).head(15), x="symbol", y="Win_Rate", text="Trades", title="Top 15 Stocks by Win Rate"), "stock_winrate", 360)
        st.dataframe(stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    st.subheader("📏 GAP Analysis")
    if actual.empty or "gap_percent" not in actual.columns:
        st.info("No recorded GAP data yet.")
    else:
        gap = actual.copy()
        gap["Gap Magnitude %"] = gap["gap_percent"].abs()
        a, b = st.columns(2)
        with a:
            chart(px.histogram(gap, x="Gap Magnitude %", nbins=12, title="Qualifying GAP Magnitude Distribution"), "gap_distribution")
        with b:
            bands = pd.cut(gap["Gap Magnitude %"], bins=[-0.0001, 0.25, 0.75, float("inf")], labels=["<0.25%", "0.25–0.75%", ">0.75%"])
            gap_band = gap.assign(Band=bands).groupby("Band", observed=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda z: (z > 0).mean() * 100), PnL=("pnl", "sum")).reset_index()
            chart(px.bar(gap_band, x="Band", y="Win_Rate", text="Trades", title="Win Rate by GAP Magnitude"), "gap_winrate")
        chart(px.scatter(gap, x="Gap Magnitude %", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in gap.columns], title="GAP Magnitude vs Trade P&L"), "gap_pnl")

with tabs[5]:
    st.subheader("⚖️ Risk & Reward")
    if actual.empty:
        st.info("No completed risk data yet.")
    else:
        a, b = st.columns(2)
        with a:
            if "rr" in actual.columns:
                chart(px.histogram(actual, x="rr", nbins=12, title="Recorded Risk : Reward Distribution"), "rr")
        with b:
            if "risk_per_share" in actual.columns:
                chart(px.scatter(actual, x="risk_per_share", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in actual.columns], title="Risk per Share vs P&L"), "riskpnl")
        a, b = st.columns(2)
        if "mae" in actual.columns and actual["mae"].ne(0).any():
            with a:
                chart(px.scatter(actual, x="mae", y="pnl", title="MAE vs P&L"), "mae_pnl")
        if "mfe" in actual.columns and actual["mfe"].ne(0).any():
            with b:
                chart(px.scatter(actual, x="mfe", y="pnl", title="MFE vs P&L"), "mfe_pnl")

with tabs[6]:
    st.subheader("⏱️ Timing & Exit Analysis")
    if actual.empty:
        st.info("No completed timing data yet.")
    else:
        if "Hold Minutes" in actual.columns and actual["Hold Minutes"].notna().any():
            timing = actual.dropna(subset=["Hold Minutes"]).copy()
            a, b = st.columns(2)
            with a:
                chart(px.histogram(timing, x="Hold Minutes", nbins=12, title="Trade Holding Time"), "hold_distribution")
            with b:
                chart(px.scatter(timing, x="Hold Minutes", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in timing.columns], title="Holding Time vs P&L"), "hold_pnl")
        if "exit_reason" in actual.columns:
            exits = actual.groupby("exit_reason", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
            chart(px.bar(exits, x="exit_reason", y="PnL", text="Trades", title="P&L by Exit Reason"), "exit_reason_pnl")
        if "Entry DT" in actual.columns and actual["Entry DT"].notna().any():
            bucket = actual.dropna(subset=["Entry DT"]).copy()
            bucket["Entry Time"] = bucket["Entry DT"].dt.strftime("%H:%M")
            bucket = bucket.groupby("Entry Time", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
            chart(px.bar(bucket, x="Entry Time", y="PnL", text="Trades", title="P&L by Entry Time"), "entry_time_pnl")

with tabs[7]:
    st.subheader("📰 News Analysis")
    news_df = clean_strategy_columns(read_csv(NEWS))
    if news_df.empty:
        st.info("No news decisions have been recorded yet.")
    else:
        sentiment = news_df.get("news_sentiment", pd.Series("NEUTRAL", index=news_df.index)).astype(str).str.upper()
        approved = news_df.get("approved", pd.Series(False, index=news_df.index)).astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("News Decisions", len(news_df))
        n2.metric("Positive", int((sentiment == "POSITIVE").sum()))
        n3.metric("Negative", int((sentiment == "NEGATIVE").sum()))
        n4.metric("Passed", int(approved.sum()))
        chart_sent = pd.DataFrame({"Sentiment": sentiment}).value_counts().reset_index(name="Decisions")
        chart_pass = pd.DataFrame({"Decision": approved.map({True: "PASSED", False: "REJECTED"})}).value_counts().reset_index(name="Decisions")
        a, b = st.columns(2)
        with a:
            chart(px.bar(chart_sent, x="Sentiment", y="Decisions", text="Decisions", title="News Sentiment Distribution"), "news_sentiment_distribution")
        with b:
            chart(px.pie(chart_pass, names="Decision", values="Decisions", title="News Gate Passed vs Rejected"), "news_gate_mix")
        cols = [c for c in ["TradeDate", "timestamp", "symbol", "signal", "news_headline", "news_sentiment", "news_confidence", "news_reason", "approved", "candidate_id", "entry", "priority_rank"] if c in news_df.columns]
        st.dataframe(news_df[cols].iloc[::-1] if cols else news_df.iloc[::-1], width="stretch", hide_index=True, height=420)

with tabs[8]:
    st.subheader("📋 Closed Trades")
    if actual.empty:
        st.info("No completed paper trades yet.")
    else:
        columns = [c for c in ["entry_time", "exit_time", "symbol", "signal", "setup_type", "entry", "stop_loss", "target", "quantity", "risk", "actual_risk", "pnl", "rr", "Result", "exit_reason"] if c in actual.columns]
        st.dataframe(actual[columns].iloc[::-1], width="stretch", hide_index=True, height=560)

st.caption("Read-only analysis • Paper trading only • Recorded price-action, GAP, risk and news data only")
render_daily_footer()
