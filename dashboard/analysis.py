"""Read-only performance dashboard for the NIFTY 500 open-reversal strategy."""
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
    try: return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError): return pd.DataFrame()


def prepare(df):
    if df.empty: return df
    df = df.copy()
    for col in ["entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl"]:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["Result"] = df["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    return df


def stats(df):
    if df.empty: return {"Trades": 0, "Wins": 0, "Losses": 0, "Win Rate %": 0.0, "P&L": 0.0, "Avg P&L": 0.0, "Profit Factor": 0.0}
    pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0); wins = pnl[pnl > 0]; losses = pnl[pnl < 0]
    return {"Trades": len(df), "Wins": int((pnl > 0).sum()), "Losses": int((pnl < 0).sum()), "Win Rate %": round(float((pnl > 0).mean() * 100), 2), "P&L": round(float(pnl.sum()), 2), "Avg P&L": round(float(pnl.mean()), 2), "Profit Factor": round(float(wins.sum() / abs(losses.sum())), 3) if not losses.empty else 0.0}


def chart(fig, key, height=340):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=55, b=12))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False}, key=key)


trades = prepare(read_csv(TRADES)); signals = read_csv(SIGNALS)
if not trades.empty and "status" in trades.columns:
    actual = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    actual = pd.DataFrame()

s = stats(actual)

st.title("📊 NIFTY 500 Strategy Analysis")
st.caption("PDH/PDL reaction → today's Open 1-minute reversal. Only closed paper trades are included in actual performance.")

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
    st.info("No closed trades yet. The dashboard will populate after the first completed paper trade.")
else:
    time_col = next((c for c in ["exit_time", "entry_time"] if c in actual.columns), None)
    if time_col:
        actual["_time"] = pd.to_datetime(actual[time_col], errors="coerce")
        actual = actual.sort_values("_time")
    actual["Trade #"] = range(1, len(actual) + 1)
    actual["Cumulative P&L"] = actual["pnl"].cumsum()
    actual["Drawdown"] = actual["Cumulative P&L"] - actual["Cumulative P&L"].cummax()

    st.subheader("P&L")
    left, right = st.columns(2)
    with left: chart(px.line(actual, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L"), "cumulative_pnl")
    with right: chart(px.bar(actual, x="Trade #", y="pnl", title="Trade P&L"), "trade_pnl")

    left, right = st.columns(2)
    with left: chart(px.line(actual, x="Trade #", y="Drawdown", markers=True, title="Drawdown"), "drawdown")
    with right: chart(px.bar(actual, x="signal", y="pnl", title="P&L by BUY / SELL"), "side_pnl")

    st.subheader("Stock Performance")
    by_stock = actual.groupby("symbol", as_index=False).agg(Trades=("symbol", "size"), PnL=("pnl", "sum")).sort_values("PnL", ascending=False)
    left, right = st.columns(2)
    with left: chart(px.bar(by_stock.head(20), x="symbol", y="PnL", text="Trades", title="Top Stocks by P&L"), "stock_pnl", 380)
    with right: st.dataframe(by_stock, width="stretch", hide_index=True, height=380)

    st.subheader("Market / Sector / Setup")
    for column in ["market_direction", "sector_direction", "stock_today_direction", "setup_type", "exit_reason"]:
        if column in actual.columns:
            grouped = actual.groupby(column, dropna=False)["pnl"].agg(["count", "sum"]).reset_index().sort_values("sum", ascending=False)
            if not grouped.empty:
                chart(px.bar(grouped, x=column, y="sum", text="count", title=f"P&L by {column.replace('_', ' ').title()}"), f"group_{column}", 320)

st.subheader("Scanner Signals")
if signals.empty:
    st.info("No approved scanner signals recorded yet.")
else:
    st.dataframe(signals.iloc[::-1], width="stretch", hide_index=True)

st.divider()
st.caption("Paper-trading research only. No live orders are enabled.")
