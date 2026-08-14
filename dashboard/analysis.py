"""Read-only performance analysis for the NIFTY 500 open-reversal paper strategy."""
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "outputs" / "trades.csv"
SIGNALS = ROOT / "outputs" / "signals.csv"
STARTING_CAPITAL = 250000.0

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")


def read_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def inject_style():
    st.markdown("""
    <style>
    html,body,[class*="css"],.stApp,.stApp *{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}
    h1,h2,h3,h4,h5,h6{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-weight:700!important}
    h1{color:#00E5FF!important;font-size:2rem!important}h2,h3,h4,h5,h6{color:#F4F7FB!important}
    p,.stCaption,.stMarkdown,.stText,label{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}
    .stCaption{color:#9FB0C7!important;font-size:.78rem!important}
    button,.stButton>button,.stDownloadButton>button{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;font-weight:600!important;border-radius:8px!important}
    </style>
    """, unsafe_allow_html=True)


def prepare(df):
    if df.empty:
        return df
    df = df.copy()
    numeric = ["entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "risk_per_share", "actual_risk", "position_value"]
    for col in numeric:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Result"] = df["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    return df


def stats(df):
    if df.empty:
        return {"Trades": 0, "Wins": 0, "Losses": 0, "Win Rate %": 0.0, "P&L": 0.0, "Avg P&L": 0.0, "Profit Factor": 0.0}
    pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    return {
        "Trades": len(df), "Wins": int((pnl > 0).sum()), "Losses": int((pnl < 0).sum()),
        "Win Rate %": round(float((pnl > 0).mean() * 100), 2), "P&L": round(float(pnl.sum()), 2),
        "Avg P&L": round(float(pnl.mean()), 2),
        "Profit Factor": round(float(wins.sum() / abs(losses.sum())), 3) if not losses.empty else 0.0,
    }


def chart(fig, key, height=330):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=55, b=12), template="plotly_dark", font=dict(family="Inter, sans-serif"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False}, key=key)


inject_style()
trades = prepare(read_csv(TRADES))
signals = read_csv(SIGNALS)
if not trades.empty and "status" in trades.columns:
    actual = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    actual = pd.DataFrame()

s = stats(actual)
st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("PDH/PDL reaction → today's Open 1-minute reversal. Closed paper trades only; no live orders.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}")
c2.metric("Closed Trades", s["Trades"])
c3.metric("Net P&L", f"₹{s['P&L']:,.2f}")
c4.metric("Current Equity", f"₹{STARTING_CAPITAL + s['P&L']:,.2f}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Win Rate", f"{s['Win Rate %']:.1f}%")
c2.metric("Wins", s["Wins"])
c3.metric("Losses", s["Losses"])
c4.metric("Profit Factor", f"{s['Profit Factor']:.2f}")

if actual.empty:
    st.info("No closed trades yet. Charts will populate automatically after completed paper trades.")
else:
    time_col = next((c for c in ["exit_time", "entry_time"] if c in actual.columns), None)
    if time_col:
        actual["_time"] = pd.to_datetime(actual[time_col], errors="coerce")
        actual = actual.sort_values("_time")
    actual["Trade #"] = range(1, len(actual) + 1)
    actual["Cumulative P&L"] = actual["pnl"].cumsum()
    actual["Peak Equity P&L"] = actual["Cumulative P&L"].cummax()
    actual["Drawdown"] = actual["Cumulative P&L"] - actual["Peak Equity P&L"]

    st.subheader("Performance Charts")
    a, b = st.columns(2)
    with a: chart(px.line(actual, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "cumulative_pnl")
    with b: chart(px.bar(actual, x="Trade #", y="pnl", title="P&L per Trade"), "trade_pnl")
    a, b = st.columns(2)
    with a: chart(px.line(actual, x="Trade #", y="Drawdown", markers=True, title="Drawdown"), "drawdown")
    with b:
        result_counts = actual["Result"].value_counts().rename_axis("Result").reset_index(name="Trades")
        chart(px.pie(result_counts, names="Result", values="Trades", title="Win / Loss / Flat Mix"), "result_mix")

    if "_time" in actual.columns and actual["_time"].notna().any():
        daily = actual.dropna(subset=["_time"]).assign(Date=actual.dropna(subset=["_time"])["_time"].dt.strftime("%d %b"))
        daily = daily.groupby("Date", sort=False, as_index=False)["pnl"].sum()
        st.subheader("Time Analysis")
        a, b = st.columns(2)
        with a: chart(px.bar(daily, x="Date", y="pnl", title="Daily P&L"), "daily_pnl")
        if "entry_time" in actual.columns and "exit_time" in actual.columns:
            entry_t = pd.to_datetime(actual["entry_time"], errors="coerce")
            exit_t = pd.to_datetime(actual["exit_time"], errors="coerce")
            actual["Duration (min)"] = (exit_t - entry_t).dt.total_seconds() / 60
            duration = actual.dropna(subset=["Duration (min)"]).copy()
            with b:
                if not duration.empty:
                    chart(px.bar(duration, x="Trade #", y="Duration (min)", title="Trade Duration"), "duration")

    st.subheader("Direction & Setup Analysis")
    a, b = st.columns(2)
    if "signal" in actual.columns:
        side = actual.groupby("signal", as_index=False)["pnl"].agg(["count", "sum"]).reset_index()
        with a: chart(px.bar(side, x="signal", y="sum", text="count", title="P&L by BUY / SELL"), "side_pnl")
    if "setup_type" in actual.columns:
        setup = actual.groupby("setup_type", dropna=False)["pnl"].agg(["count", "sum"]).reset_index().sort_values("sum", ascending=False)
        with b: chart(px.bar(setup, x="setup_type", y="sum", text="count", title="P&L by Setup"), "setup_pnl")

    st.subheader("Stock Performance")
    if "symbol" in actual.columns:
        by_stock = actual.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum")).sort_values("PnL", ascending=False)
        a, b = st.columns(2)
        with a: chart(px.bar(by_stock.head(20), x="symbol", y="PnL", text="Trades", title="Top Stocks by P&L"), "stock_pnl", 380)
        with b: chart(px.bar(by_stock.tail(20).sort_values("PnL"), x="symbol", y="PnL", text="Trades", title="Weakest Stocks by P&L"), "weak_stock_pnl", 380)
        st.dataframe(by_stock, width="stretch", hide_index=True, height=360)

    st.subheader("Market / Sector / Exit Analysis")
    group_cols = ["market_direction", "sector_direction", "stock_today_direction", "exit_reason"]
    available = [c for c in group_cols if c in actual.columns]
    for i in range(0, len(available), 2):
        cols = st.columns(2)
        for j, column in enumerate(available[i:i+2]):
            grouped = actual.groupby(column, dropna=False)["pnl"].agg(["count", "sum"]).reset_index().sort_values("sum", ascending=False)
            if not grouped.empty:
                with cols[j]:
                    chart(px.bar(grouped, x=column, y="sum", text="count", title=f"P&L by {column.replace('_', ' ').title()}"), f"group_{column}", 320)

    st.subheader("Risk & Reward Analysis")
    a, b = st.columns(2)
    if "rr" in actual.columns:
        rr = actual.copy()
        rr["RR"] = pd.to_numeric(rr["rr"], errors="coerce").fillna(0)
        with a: chart(px.histogram(rr, x="RR", nbins=12, title="Risk : Reward Distribution"), "rr_distribution")
    if "risk_per_share" in actual.columns and "pnl" in actual.columns:
        with b: chart(px.scatter(actual, x="risk_per_share", y="pnl", hover_data=["symbol"] if "symbol" in actual.columns else None, title="Risk per Share vs P&L"), "risk_pnl")

    st.subheader("Complete Closed-Trade Analysis Table")
    display_cols = [c for c in ["Trade #", "entry_time", "exit_time", "symbol", "signal", "entry", "stop_loss", "target", "quantity", "risk_per_share", "rr", "pnl", "Result", "exit_reason"] if c in actual.columns]
    st.dataframe(actual[display_cols].iloc[::-1], width="stretch", hide_index=True, height=420)

st.subheader("Scanner Signals")
if signals.empty:
    st.info("No approved scanner signals recorded yet.")
else:
    st.dataframe(signals.iloc[::-1], width="stretch", hide_index=True, height=420)

st.divider()
st.caption("Paper-trading research only. Live trading is disabled.")
