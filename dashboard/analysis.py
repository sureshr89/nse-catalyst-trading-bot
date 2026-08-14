"""Read-only performance analysis for the NIFTY 500 paper strategy."""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dashboard.style import load_css

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "outputs" / "trades.csv"
SIGNALS = ROOT / "outputs" / "signals.csv"
STARTING_CAPITAL = 250000.0
st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)


def read_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def prepare(df):
    if df.empty:
        return df
    df = df.copy()
    for col in ["entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "risk_per_share", "actual_risk", "position_value"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Result"] = df["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    return df


def stats(df):
    if df.empty:
        return 0, 0, 0, 0.0, 0.0, 0.0
    pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    return len(df), int((pnl > 0).sum()), int((pnl < 0).sum()), float((pnl > 0).mean() * 100), float(pnl.sum()), float(wins.sum() / abs(losses.sum())) if not losses.empty else 0.0


def chart(fig, key, height=310):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=45, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", size=12), hovermode=False)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False, "staticPlot": True, "responsive": True}, key=key)


def empty_chart(title, key, height=310):
    fig = go.Figure()
    fig.update_layout(height=height, template="plotly_dark", title=title, margin=dict(l=8, r=8, t=45, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(visible=False), yaxis=dict(visible=False))
    fig.add_annotation(text="No completed paper-trade data yet", x=.5, y=.5, xref="paper", yref="paper", showarrow=False)
    chart(fig, key, height)


def grouped_chart(df, column, title, key, height=300):
    if not df.empty and column in df.columns:
        g = df.groupby(column, dropna=False)["pnl"].agg(["count", "sum"]).reset_index()
        chart(px.bar(g, x=column, y="sum", text="count", title=title), key, height)
    else:
        empty_chart(title, key, height)


trades = prepare(read_csv(TRADES))
signals = read_csv(SIGNALS)
actual = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
count, wins, losses, win_rate, pnl_total, profit_factor = stats(actual)
if not actual.empty:
    tc = next((c for c in ["exit_time", "entry_time"] if c in actual.columns), None)
    if tc:
        actual["_time"] = pd.to_datetime(actual[tc], errors="coerce")
        actual = actual.sort_values("_time")
    actual["Trade #"] = range(1, len(actual) + 1)
    actual["Cumulative P&L"] = actual["pnl"].cumsum()
    actual["Drawdown"] = actual["Cumulative P&L"] - actual["Cumulative P&L"].cummax()

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("PDH/PDL reaction → today's Open 1-minute reversal • Closed paper trades only • No live orders")
kpis = [("Starting Capital", f"₹{STARTING_CAPITAL:,.0f}"), ("Closed Trades", count), ("Net P&L", f"₹{pnl_total:,.2f}"), ("Current Equity", f"₹{STARTING_CAPITAL+pnl_total:,.2f}"), ("Win Rate", f"{win_rate:.1f}%"), ("Wins", wins), ("Losses", losses), ("Profit Factor", f"{profit_factor:.2f}")]
st.markdown('<div class="analysis-kpi-grid">' + ''.join(f'<div class="analysis-kpi"><span>{a}</span><strong>{b}</strong></div>' for a,b in kpis) + '</div>', unsafe_allow_html=True)

tabs = st.tabs(["📌 Overview", "💰 P&L", "⏱️ Time", "🎯 Setup", "🏆 Stocks", "🌐 Market", "⚖️ Risk / Reward", "📋 Trades"])

with tabs[0]:
    st.subheader("Performance Overview")
    a,b = st.columns(2)
    with a:
        if actual.empty: empty_chart("Cumulative P&L", "ov_cum")
        else: chart(px.line(actual, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "ov_cum")
    with b:
        if actual.empty: empty_chart("Drawdown", "ov_dd")
        else: chart(px.line(actual, x="Trade #", y="Drawdown", markers=True, title="Drawdown"), "ov_dd")
    a,b = st.columns(2)
    with a:
        if actual.empty: empty_chart("Win / Loss / Flat Mix", "ov_mix")
        else:
            c = actual["Result"].value_counts().rename_axis("Result").reset_index(name="Trades")
            chart(px.pie(c, names="Result", values="Trades", title="Win / Loss / Flat Mix"), "ov_mix")
    with b:
        if actual.empty: empty_chart("P&L per Trade", "ov_trade")
        else: chart(px.bar(actual, x="Trade #", y="pnl", title="P&L per Trade"), "ov_trade")

with tabs[1]:
    st.subheader("P&L Analysis")
    a,b = st.columns(2)
    if not actual.empty and "_time" in actual.columns:
        d = actual.dropna(subset=["_time"]).copy(); d["Date"] = d["_time"].dt.strftime("%d %b"); d = d.groupby("Date", sort=False, as_index=False)["pnl"].sum()
        with a: chart(px.bar(d, x="Date", y="pnl", title="Daily P&L"), "pnl_day")
    else:
        with a: empty_chart("Daily P&L", "pnl_day")
    with b:
        if actual.empty: empty_chart("P&L per Trade", "pnl_trade")
        else: chart(px.bar(actual, x="Trade #", y="pnl", title="P&L per Trade"), "pnl_trade")
    if not actual.empty: st.dataframe(actual[["Trade #","pnl","Result"]].iloc[::-1], use_container_width=True, hide_index=True, height=300)

with tabs[2]:
    st.subheader("Time Analysis")
    a,b = st.columns(2)
    if not actual.empty and "entry_time" in actual.columns and "exit_time" in actual.columns:
        x = actual.copy(); x["Duration (min)"] = (pd.to_datetime(x["exit_time"], errors="coerce")-pd.to_datetime(x["entry_time"], errors="coerce")).dt.total_seconds()/60; x=x.dropna(subset=["Duration (min)"])
        with a:
            if x.empty: empty_chart("Trade Duration", "time_dur")
            else: chart(px.bar(x, x="Trade #", y="Duration (min)", title="Trade Duration"), "time_dur")
    else:
        with a: empty_chart("Trade Duration", "time_dur")
    if not actual.empty and "_time" in actual.columns:
        x=actual.dropna(subset=["_time"]).copy(); x["Time"]=x["_time"].dt.strftime("%H:%M"); x=x.groupby("Time",as_index=False)["pnl"].sum()
        with b: chart(px.bar(x,x="Time",y="pnl",title="P&L by Exit Time"),"time_exit") if not x.empty else empty_chart("P&L by Exit Time","time_exit")
    else:
        with b: empty_chart("P&L by Exit Time", "time_exit")

with tabs[3]:
    st.subheader("Direction & Setup Analysis")
    a,b=st.columns(2); grouped_chart(actual,"signal","P&L by BUY / SELL","setup_side"); grouped_chart(actual,"setup_type","P&L by Setup","setup_type")
    a,b=st.columns(2)
    with a: grouped_chart(actual,"exit_reason","P&L by Exit Reason","setup_exit")
    with b: grouped_chart(actual,"stock_today_direction","P&L by Stock Direction","setup_stock")

with tabs[4]:
    st.subheader("Stock Performance")
    if not actual.empty and "symbol" in actual.columns:
        by_stock=actual.groupby("symbol",as_index=False).agg(Trades=("symbol","size"),PnL=("pnl","sum")).sort_values("PnL",ascending=False)
        a,b=st.columns(2)
        with a: chart(px.bar(by_stock.head(20),x="symbol",y="PnL",text="Trades",title="Top Stocks by P&L"),"stock_top",360)
        with b: chart(px.bar(by_stock.tail(20).sort_values("PnL"),x="symbol",y="PnL",text="Trades",title="Weakest Stocks by P&L"),"stock_weak",360)
        st.dataframe(by_stock,use_container_width=True,hide_index=True,height=360)
    else:
        a,b=st.columns(2)
        with a: empty_chart("Top Stocks by P&L","stock_top",360)
        with b: empty_chart("Weakest Stocks by P&L","stock_weak",360)

with tabs[5]:
    st.subheader("Market / Sector / Exit Analysis")
    a,b=st.columns(2)
    with a: grouped_chart(actual,"market_direction","P&L by Market Direction","market_dir")
    with b: grouped_chart(actual,"sector_direction","P&L by Sector Direction","market_sector")
    a,b=st.columns(2)
    with a: grouped_chart(actual,"stock_today_direction","P&L by Stock Direction","market_stock")
    with b: grouped_chart(actual,"exit_reason","P&L by Exit Reason","market_exit")

with tabs[6]:
    st.subheader("Risk & Reward Analysis")
    a,b=st.columns(2)
    with a:
        if not actual.empty and "rr" in actual.columns: chart(px.histogram(actual,x="rr",nbins=12,title="Risk : Reward Distribution"),"risk_rr")
        else: empty_chart("Risk : Reward Distribution","risk_rr")
    with b:
        if not actual.empty and "risk_per_share" in actual.columns: chart(px.scatter(actual,x="risk_per_share",y="pnl",title="Risk per Share vs P&L"),"risk_pnl")
        else: empty_chart("Risk per Share vs P&L","risk_pnl")
    a,b=st.columns(2)
    with a:
        if not actual.empty and "actual_risk" in actual.columns: chart(px.histogram(actual,x="actual_risk",nbins=12,title="Actual Risk Distribution"),"risk_actual")
        else: empty_chart("Actual Risk Distribution","risk_actual")
    with b:
        if not actual.empty and "reward" in actual.columns: chart(px.histogram(actual,x="reward",nbins=12,title="Reward Distribution"),"risk_reward")
        else: empty_chart("Reward Distribution","risk_reward")

with tabs[7]:
    st.subheader("Closed Trades & Scanner Signals")
    if not actual.empty:
        cols=[c for c in ["Trade #","entry_time","exit_time","symbol","signal","entry","stop_loss","target","quantity","risk_per_share","rr","pnl","Result","exit_reason"] if c in actual.columns]
        st.dataframe(actual[cols].iloc[::-1],use_container_width=True,hide_index=True,height=430)
    else: st.info("No closed paper trades yet. The complete trade table will populate automatically.")
    st.markdown("### Scanner Signals")
    if signals.empty: st.info("No approved scanner signals recorded yet.")
    else: st.dataframe(signals.iloc[::-1],use_container_width=True,hide_index=True,height=430)

st.divider(); st.caption("Paper-trading research only. Live trading is disabled.")
