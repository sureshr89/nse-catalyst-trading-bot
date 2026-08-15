"""Page 3: comprehensive read-only analysis for the current strategy."""
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


def analysis_text(actual):
    if actual.empty:
        return
    avg_win = float(actual.loc[actual["pnl"] > 0, "pnl"].mean()) if (actual["pnl"] > 0).any() else 0.0
    avg_loss = float(actual.loc[actual["pnl"] < 0, "pnl"].mean()) if (actual["pnl"] < 0).any() else 0.0
    best = actual.loc[actual["pnl"].idxmax()]
    worst = actual.loc[actual["pnl"].idxmin()]
    st.markdown("### 🔍 Automatic Performance Reading")
    c1, c2, c3 = st.columns(3)
    c1.metric("Average winning trade", f"₹{avg_win:,.2f}")
    c2.metric("Average losing trade", f"₹{avg_loss:,.2f}")
    c3.metric("Best / Worst", f"₹{best['pnl']:,.0f} / ₹{worst['pnl']:,.0f}")
    observations = []
    if avg_win and avg_loss:
        observations.append(f"Average win is ₹{avg_win:,.0f}; average loss is ₹{abs(avg_loss):,.0f}.")
    if best.get("symbol", ""):
        observations.append(f"Best recorded trade: {best.get('symbol', '')} ({best.get('signal', '')}) with ₹{best['pnl']:,.2f}.")
    if worst.get("symbol", ""):
        observations.append(f"Worst recorded trade: {worst.get('symbol', '')} ({worst.get('signal', '')}) with ₹{worst['pnl']:,.2f}.")
    if "signal" in actual.columns:
        side = actual.groupby("signal")["pnl"].agg(Trades="size", PnL="sum")
        if len(side):
            best_side = side["PnL"].idxmax()
            observations.append(f"The stronger side by total P&L is {best_side}.")
    for item in observations:
        st.write("• " + item)


df = read_csv(TRADES)
if not df.empty:
    for column in [
        "pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr",
        "gap_percent", "atr_pct", "actual_risk", "risk_per_share", "mae", "mfe",
    ]:
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
flats = int((actual["pnl"] == 0).sum()) if count else 0
net = float(actual["pnl"].sum()) if count else 0.0
winrate = wins / count * 100 if count else 0.0
loss_sum = abs(float(actual.loc[actual["pnl"] < 0, "pnl"].sum())) if count else 0.0
gross_profit = float(actual.loc[actual["pnl"] > 0, "pnl"].sum()) if count else 0.0
pf = gross_profit / loss_sum if loss_sum else 0.0
max_dd = abs(float(actual["Drawdown"].min())) if count else 0.0
avg_trade = net / count if count else 0.0

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("Comprehensive closed-trade analysis • PDH/PDL + Today's Open Return strategy")
cards([
    ("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"),
    ("Closed Trades", count),
    ("Net P&L", f"₹{net:,.2f}"),
    ("Current Equity", f"₹{STARTING_CAPITAL + net:,.2f}"),
    ("Win Rate", f"{winrate:.1f}%"),
    ("Profit Factor", f"{pf:.2f}"),
    ("Average Trade", f"₹{avg_trade:,.2f}"),
    ("Max Drawdown", f"₹{max_dd:,.2f}"),
])

st.subheader("⚡ Strategy Rules Being Analysed")
st.dataframe(
    pd.DataFrame([
        ("Universe", "NIFTY 500"),
        ("BUY setup", "Today's Open > PDH → completed 1m close below PDH → completed 1m close back to Today's Open"),
        ("SELL setup", "Today's Open < PDL → completed 1m close above PDL → completed 1m close back to Today's Open"),
        ("Market filter", "BUY ≥ +0.25% NIFTY 500 • SELL ≤ −0.25% NIFTY 500"),
        ("Entry window", "09:45–14:00 IST"),
        ("Risk", "SL at PDH/PDL • target at 1.25R • ₹1,400–₹1,500 intended risk"),
        ("Ranking", "ATR% priority after price-action qualification"),
        ("News gate", "BUY requires POSITIVE news • SELL requires NEGATIVE news"),
    ], columns=["Rule", "Definition"]),
    width="stretch",
    hide_index=True,
)

tabs = st.tabs([
    "📌 Overview", "💰 P&L", "🎯 Setup", "🏆 Stocks", "📈 ATR", "⚖️ Risk / Reward",
    "⏱️ Timing", "📰 News Analysis", "📋 Trades"
])

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
            result_counts = actual["Result"].value_counts().rename_axis("Result").reset_index(name="Trades")
            chart(px.pie(result_counts, names="Result", values="Trades", title="Trade Outcome Mix"), "mix")
        with b:
            result_pnl = actual.groupby("Result", as_index=False)["pnl"].sum()
            chart(px.bar(result_pnl, x="Result", y="pnl", text="pnl", title="P&L Contribution by Outcome"), "result_pnl")
        analysis_text(actual)

with tabs[1]:
    st.subheader("💰 Detailed P&L Analysis")
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
        else:
            with a:
                chart(px.bar(actual, x="Trade #", y="pnl", title="P&L per Trade"), "pnl_by_trade")
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
            side = actual.groupby("signal", as_index=False).agg(
                Trades=("pnl", "size"),
                Win_Rate=("pnl", lambda z: (z > 0).mean() * 100),
                PnL=("pnl", "sum"),
            )
            with a:
                chart(px.bar(side, x="signal", y="Win_Rate", text="Trades", title="Win Rate by Side"), "side_winrate")
        if "setup_type" in actual.columns:
            setup = actual.groupby("setup_type", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
            with b:
                chart(px.bar(setup, x="setup_type", y="PnL", text="Trades", title="P&L by Setup Type"), "setup_type_pnl")
        if "gap_percent" in actual.columns:
            gap = actual.copy()
            gap["Gap Band"] = pd.cut(
                gap["gap_percent"].abs(),
                bins=[-0.0001, 0.25, 0.75, float("inf")],
                labels=["<0.25%", "0.25–0.75%", ">0.75%"],
            )
            gap_summary = gap.groupby("Gap Band", observed=False).agg(
                Trades=("pnl", "size"),
                Win_Rate=("pnl", lambda z: (z > 0).mean() * 100),
                Net_PnL=("pnl", "sum"),
            ).reset_index()
            st.dataframe(gap_summary, width="stretch", hide_index=True)
            chart(px.bar(gap_summary, x="Gap Band", y="Win_Rate", text="Trades", title="Win Rate by Gap Size"), "gap_winrate")

with tabs[3]:
    st.subheader("🏆 Stock-Level Performance")
    if actual.empty or "symbol" not in actual.columns:
        st.info("No completed stock-level results yet.")
    else:
        stock = actual.groupby("symbol", as_index=False).agg(
            Trades=("symbol", "size"),
            PnL=("pnl", "sum"),
            Win_Rate=("pnl", lambda z: (z > 0).mean() * 100),
        ).sort_values("PnL", ascending=False)
        a, b = st.columns(2)
        with a:
            chart(px.bar(stock.head(15), x="symbol", y="PnL", text="Trades", title="Top 15 Stocks by P&L"), "topstocks", 360)
        with b:
            chart(px.bar(stock.tail(15).sort_values("PnL"), x="symbol", y="PnL", text="Trades", title="Bottom 15 Stocks by P&L"), "weakstocks", 360)
        st.subheader("Stock Win Rate")
        chart(px.bar(stock.sort_values("Win_Rate", ascending=False).head(15), x="symbol", y="Win_Rate", text="Trades", title="Top 15 Stocks by Win Rate"), "stock_winrate", 360)
        st.dataframe(stock, width="stretch", hide_index=True, height=360)

with tabs[4]:
    st.subheader("📈 ATR Analysis")
    if actual.empty or "atr_pct" not in actual.columns or actual["atr_pct"].eq(0).all():
        st.info("ATR data is not available in the recorded closed trades yet.")
    else:
        atr = actual[actual["atr_pct"] > 0].copy()
        a, b = st.columns(2)
        with a:
            chart(px.histogram(atr, x="atr_pct", nbins=12, title="ATR% Distribution of Taken Trades"), "atr_distribution")
        with b:
            atr["ATR Band"] = pd.qcut(atr["atr_pct"], q=min(4, atr["atr_pct"].nunique()), duplicates="drop")
            atr_band = atr.groupby("ATR Band", observed=False).agg(
                Trades=("pnl", "size"),
                Win_Rate=("pnl", lambda z: (z > 0).mean() * 100),
                PnL=("pnl", "sum"),
            ).reset_index()
            chart(px.bar(atr_band, x="ATR Band", y="Win_Rate", text="Trades", title="Win Rate by ATR Band"), "atr_winrate")
        chart(px.scatter(atr, x="atr_pct", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in atr.columns], title="ATR% vs Trade P&L"), "atr_pnl")

with tabs[5]:
    st.subheader("⚖️ Risk & Reward Analysis")
    if actual.empty:
        st.info("No completed risk data yet.")
    else:
        a, b = st.columns(2)
        with a:
            if "rr" in actual.columns:
                chart(px.histogram(actual, x="rr", nbins=12, title="Recorded Risk : Reward Distribution"), "rr")
            else:
                st.info("No R:R data recorded yet.")
        with b:
            if "risk_per_share" in actual.columns:
                chart(px.scatter(actual, x="risk_per_share", y="pnl", hover_data=[c for c in ["symbol", "signal"] if c in actual.columns], title="Risk per Share vs P&L"), "riskpnl")
            else:
                st.info("No risk-per-share data recorded yet.")
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
            time_bucket = actual.dropna(subset=["Entry DT"]).copy()
            time_bucket["Entry Hour"] = time_bucket["Entry DT"].dt.strftime("%H:%M")
            time_bucket = time_bucket.groupby("Entry Hour", as_index=False).agg(Trades=("pnl", "size"), PnL=("pnl", "sum"))
            chart(px.bar(time_bucket, x="Entry Hour", y="PnL", text="Trades", title="P&L by Entry Time"), "entry_time_pnl")

with tabs[7]:
    st.subheader("📰 News Analysis")
    st.caption("Recorded news decisions attached to candidate timestamps. This page analyses the stored decisions; it does not invent missing news data.")
    news_df = read_csv(NEWS)
    if news_df.empty:
        st.info("No news decisions have been recorded yet. Charts will populate when qualified candidates reach the news gate.")
    else:
        sentiment = news_df.get("news_sentiment", pd.Series("NEUTRAL", index=news_df.index)).astype(str).str.upper()
        approved_bool = news_df.get("approved", pd.Series(False, index=news_df.index)).astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("News Decisions", len(news_df))
        n2.metric("Positive", int((sentiment == "POSITIVE").sum()))
        n3.metric("Negative", int((sentiment == "NEGATIVE").sum()))
        n4.metric("Passed", int(approved_bool.sum()))
        chart_sent = pd.DataFrame({"Sentiment": sentiment}).value_counts().reset_index(name="Decisions")
        chart_pass = pd.DataFrame({"Decision": approved_bool.map({True: "PASSED", False: "REJECTED"})}).value_counts().reset_index(name="Decisions")
        a, b = st.columns(2)
        with a:
            chart(px.bar(chart_sent, x="Sentiment", y="Decisions", text="Decisions", title="News Sentiment Distribution"), "news_sentiment_distribution", 320)
        with b:
            chart(px.pie(chart_pass, names="Decision", values="Decisions", title="News Gate Passed vs Rejected"), "news_gate_mix", 320)
        if "news_confidence" in news_df.columns:
            confidence = pd.to_numeric(news_df["news_confidence"], errors="coerce").dropna()
            if not confidence.empty:
                chart(px.histogram(pd.DataFrame({"Confidence": confidence}), x="Confidence", nbins=10, title="News Confidence Distribution"), "news_confidence", 320)
        view = news_df.copy()
        if "timestamp" in view.columns:
            view["timestamp_dt"] = pd.to_datetime(view["timestamp"], errors="coerce")
            view["TradeDate"] = view["timestamp_dt"].dt.strftime("%Y-%m-%d")
        else:
            view["TradeDate"] = ""
        f1, f2 = st.columns(2)
        with f1:
            selected_sentiment = st.multiselect("Sentiment", ["POSITIVE", "NEGATIVE", "NEUTRAL"], default=["POSITIVE", "NEGATIVE", "NEUTRAL"], key="analysis_news_sentiment")
        with f2:
            side_options = sorted(view["signal"].dropna().astype(str).str.upper().unique().tolist()) if "signal" in view.columns else []
            selected_side = st.multiselect("Side", side_options, default=side_options, key="analysis_news_side")
        if selected_sentiment:
            view = view[sentiment.loc[view.index].isin(selected_sentiment)]
        if selected_side and "signal" in view.columns:
            view = view[view["signal"].astype(str).str.upper().isin(selected_side)]
        cols = [c for c in ["TradeDate", "timestamp", "symbol", "signal", "news_headline", "news_sentiment", "news_confidence", "news_reason", "approved", "candidate_id", "entry", "priority_rank"] if c in view.columns]
        st.dataframe(view[cols].sort_values(["TradeDate", "timestamp"], ascending=False) if cols else view, width="stretch", hide_index=True, height=420)
        st.download_button("⬇️ DOWNLOAD NEWS ANALYSIS CSV", data=view.to_csv(index=False).encode("utf-8"), file_name="nse_catalyst_news_analysis.csv", mime="text/csv", width="stretch")

with tabs[8]:
    st.subheader("📋 Closed Trades")
    if actual.empty:
        st.info("No completed paper trades yet.")
    else:
        columns = [c for c in [
            "entry_time", "exit_time", "symbol", "signal", "setup_type", "entry", "stop_loss",
            "target", "quantity", "risk", "actual_risk", "pnl", "rr", "atr_pct", "Result", "exit_reason"
        ] if c in actual.columns]
        st.dataframe(actual[columns].iloc[::-1], width="stretch", hide_index=True, height=560)

st.caption("Read-only analysis • Paper trading only • Charts use recorded data only")
render_daily_footer()
