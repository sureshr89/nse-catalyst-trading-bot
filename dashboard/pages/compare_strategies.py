"""Chart-first comparison dashboard for Strategies 1-5."""
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css

st.set_page_config(page_title="NSE Catalyst | Compare", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

st.title("📊 Compare All Strategies")
st.caption("S1–S5 performance comparison • actual recorded paper trades only • no success probability is invented")

trades_path = ROOT / "outputs" / "trades.csv"
try:
    trades = pd.read_csv(trades_path)
except Exception:
    trades = pd.DataFrame()

if trades.empty:
    st.info("No recorded trades yet. The comparison charts will populate automatically after paper trades are recorded.")
    st.stop()

if "strategy" not in trades.columns:
    st.warning("Trade history does not contain a strategy column yet.")
    st.stop()

trades["strategy"] = trades["strategy"].astype(str).str.upper()
trades["strategy"] = trades["strategy"].replace({"S1":"STRATEGY_1","S2":"STRATEGY_2","S3":"STRATEGY_3","S4":"STRATEGY_4","S5":"STRATEGY_5"})
trades = trades[trades["strategy"].isin([f"STRATEGY_{i}" for i in range(1,6)])].copy()

if "status" in trades.columns:
    closed = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    closed = trades.copy()

if "pnl" not in closed.columns:
    closed["pnl"] = 0.0
closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)

side_filter = st.radio("Trade side", ["All", "BUY", "SELL"], horizontal=True)
if side_filter != "All" and "signal" in closed.columns:
    closed = closed[closed["signal"].astype(str).str.upper().eq(side_filter)].copy()

if closed.empty:
    st.info("No closed trades match the selected filter.")
    st.stop()

rows = []
for i in range(1, 6):
    name = f"STRATEGY_{i}"
    x = closed[closed["strategy"].eq(name)].copy()
    pnl = x["pnl"]
    wins = int((pnl > 0).sum())
    losses = int((pnl < 0).sum())
    total = len(x)
    gross_profit = float(pnl[pnl > 0].sum())
    gross_loss = abs(float(pnl[pnl < 0].sum()))
    equity = pnl.cumsum() if total else pd.Series(dtype=float)
    drawdown = float((equity.cummax() - equity).max()) if total else 0.0
    rows.append({
        "Strategy": f"S{i}",
        "Trades": total,
        "Wins": wins,
        "Losses": losses,
        "Win Rate %": (wins / total * 100) if total else 0.0,
        "Net P&L": float(pnl.sum()),
        "Avg P&L": float(pnl.mean()) if total else 0.0,
        "Profit Factor": gross_profit / gross_loss if gross_loss else 0.0,
        "Max Drawdown": drawdown,
    })
summary = pd.DataFrame(rows)

# KPI highlights
best_profit = summary.loc[summary["Net P&L"].idxmax()]
best_win = summary.loc[summary["Win Rate %"].idxmax()]
best_pf = summary.loc[summary["Profit Factor"].idxmax()]
lowest_dd = summary.loc[summary["Max Drawdown"].idxmin()]

cards = st.columns(4)
cards[0].metric("🏆 Highest Net P&L", best_profit["Strategy"], f"₹{best_profit['Net P&L']:,.0f}")
cards[1].metric("🎯 Highest Win Rate", best_win["Strategy"], f"{best_win['Win Rate %']:.1f}%")
cards[2].metric("💰 Best Profit Factor", best_pf["Strategy"], f"{best_pf['Profit Factor']:.2f}")
cards[3].metric("🛡️ Lowest Drawdown", lowest_dd["Strategy"], f"₹{lowest_dd['Max Drawdown']:,.0f}")

st.subheader("📈 Performance Charts")
chart1 = px.bar(summary, x="Strategy", y="Net P&L", text_auto=".0f", title="Net P&L by Strategy")
st.plotly_chart(chart1, width="stretch", config={"displayModeBar": False})

chart2 = px.bar(summary, x="Strategy", y="Win Rate %", text_auto=".1f", title="Win Rate Comparison")
st.plotly_chart(chart2, width="stretch", config={"displayModeBar": False})

chart3 = px.bar(summary, x="Strategy", y=["Wins", "Losses"], barmode="group", title="Winning vs Losing Trades")
st.plotly_chart(chart3, width="stretch", config={"displayModeBar": False})

chart4 = px.bar(summary, x="Strategy", y="Max Drawdown", text_auto=".0f", title="Maximum Drawdown")
st.plotly_chart(chart4, width="stretch", config={"displayModeBar": False})

# Cumulative P&L chart
curve_frames = []
for i in range(1, 6):
    x = closed[closed["strategy"].eq(f"STRATEGY_{i}")].copy().reset_index(drop=True)
    if x.empty:
        continue
    x["Trade"] = range(1, len(x) + 1)
    x["Cumulative P&L"] = x["pnl"].cumsum()
    x["Strategy"] = f"S{i}"
    curve_frames.append(x[["Trade", "Cumulative P&L", "Strategy"]])
if curve_frames:
    curves = pd.concat(curve_frames, ignore_index=True)
    chart5 = px.line(curves, x="Trade", y="Cumulative P&L", color="Strategy", markers=True, title="Cumulative P&L — S1 vs S2 vs S3 vs S4 vs S5")
    st.plotly_chart(chart5, width="stretch", config={"displayModeBar": False})

st.subheader("📋 Comparison Details")
display = summary.copy()
for c in ["Net P&L", "Avg P&L", "Max Drawdown"]:
    display[c] = display[c].map(lambda v: f"₹{v:,.2f}")
display["Win Rate %"] = display["Win Rate %"].map(lambda v: f"{v:.1f}%")
display["Profit Factor"] = display["Profit Factor"].map(lambda v: f"{v:.2f}")
st.dataframe(display, width="stretch", hide_index=True)

st.caption("Probability of success is intentionally not estimated from insufficient trade history. Once enough paper trades exist, statistical confidence can be added separately.")
