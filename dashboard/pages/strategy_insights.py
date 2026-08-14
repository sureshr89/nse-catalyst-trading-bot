import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Strategy Insights", page_icon="🧠", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def score_trade(row):
    score = 0
    checks = []
    market = str(row.get("market_direction", "")).upper()
    sector = str(row.get("sector_direction", "")).upper()
    stock = str(row.get("stock_direction", "")).upper()
    side = str(row.get("signal", row.get("buy_sell", ""))).upper()
    required = "BULLISH" if side == "BUY" else "BEARISH" if side == "SELL" else ""
    if required and market == required:
        score += 30; checks.append("NIFTY 500 aligned")
    if required and sector == required:
        score += 30; checks.append("Sector aligned")
    if required and stock == required:
        score += 20; checks.append("Stock aligned")
    try:
        gap = abs(float(row.get("gap_percent", 0) or 0))
        if gap > 0:
            score += 10
            checks.append(f"Gap {gap:.2f}%")
    except Exception:
        pass
    try:
        entry = pd.to_datetime(row.get("entry_time"), errors="coerce")
        if not pd.isna(entry):
            minute = entry.hour * 60 + entry.minute
            if 585 <= minute <= 615:
                score += 10; checks.append("Early-window entry")
            elif 615 < minute <= 660:
                score += 5; checks.append("Mid-morning entry")
    except Exception:
        pass
    return score, checks


trades = read_csv(ROOT / "outputs/trades.csv")
signals = read_csv(ROOT / "outputs/signals.csv")
if trades.empty and signals.empty:
    st.title("🧠 Strategy Insights")
    st.info("No paper-trading records are available yet. Insights will populate automatically after trades/signals are recorded.")
    render_daily_footer()
    st.stop()

if not trades.empty:
    trades["status"] = trades.get("status", "").astype(str).str.upper()
    closed = trades[trades["status"].eq("CLOSED")].copy()
    if not closed.empty:
        closed["pnl"] = pd.to_numeric(closed.get("pnl", 0), errors="coerce").fillna(0.0)
else:
    closed = pd.DataFrame()

st.title("🧠 Strategy Insights")
st.caption("Research-only analysis of the existing NIFTY 500 PDH/PDL → today's Open 1-minute reversal paper trades. No strategy rules are changed by this page.")

if not closed.empty:
    total = len(closed)
    wins = int((closed["pnl"] > 0).sum())
    losses = int((closed["pnl"] < 0).sum())
    gross_profit = float(closed.loc[closed["pnl"] > 0, "pnl"].sum())
    gross_loss = abs(float(closed.loc[closed["pnl"] < 0, "pnl"].sum()))
    win_rate = wins / total * 100 if total else 0
    profit_factor = gross_profit / gross_loss if gross_loss else 0
    cols = st.columns(6)
    for col, label, value in zip(cols, ["Closed Trades", "Win Rate", "Net P&L", "Profit Factor", "Wins", "Losses"], [total, f"{win_rate:.1f}%", f"₹{closed['pnl'].sum():,.2f}", f"{profit_factor:.2f}", wins, losses]):
        with col:
            st.metric(label, value)

    work = closed.copy()
    work["Quality Score"] = work.apply(lambda r: score_trade(r)[0], axis=1)
    work["Why This Trade"] = work.apply(lambda r: " • ".join(score_trade(r)[1]) or "Recorded setup context only", axis=1)

    st.subheader("Signal Quality — Display / Research Only")
    st.caption("Score is descriptive only. It does NOT approve, reject, or alter trades.")
    qcols = [c for c in ["symbol", "signal", "entry_time", "Quality Score", "Why This Trade", "pnl"] if c in work.columns]
    st.dataframe(work.sort_values("entry_time", ascending=False)[qcols].head(50), width="stretch", hide_index=True)

    st.subheader("Why the Trade Was Taken")
    latest = work.iloc[-1]
    score, reasons = score_trade(latest)
    st.markdown(f"**{latest.get('symbol','—')} {latest.get('signal', latest.get('buy_sell','—'))} — Quality {score}/100**")
    for reason in reasons:
        st.write(f"• {reason}")
    st.write(f"• Entry: ₹{float(latest.get('entry', 0) or 0):,.2f} | SL: ₹{float(latest.get('stop_loss', 0) or 0):,.2f} | Target: ₹{float(latest.get('target', 0) or 0):,.2f}")
    st.write(f"• PDH: {latest.get('pdh','—')} | PDL: {latest.get('pdl','—')} | Today's Open: {latest.get('today_open','—')}")

    st.subheader("Gap Performance")
    if "gap_percent" in work.columns:
        work["Gap %"] = pd.to_numeric(work["gap_percent"], errors="coerce")
        work["Gap Band"] = pd.cut(work["Gap %"].abs(), bins=[-0.0001, 0.25, 0.75, float("inf")], labels=["<0.25%", "0.25–0.75%", ">0.75%"])
        gap = work.groupby("Gap Band", observed=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index()
        st.dataframe(gap, width="stretch", hide_index=True)

    st.subheader("Entry-Time Performance")
    work["Entry"] = pd.to_datetime(work.get("entry_time"), errors="coerce")
    work["Entry Window"] = work["Entry"].dt.hour.fillna(0).astype(int).astype(str).str.zfill(2) + ":" + ((work["Entry"].dt.minute.fillna(0).astype(int) // 30) * 30).astype(int).astype(str).str.zfill(2)
    timing = work.groupby("Entry Window", dropna=False).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index()
    st.dataframe(timing, width="stretch", hide_index=True)

    st.subheader("BUY vs SELL")
    side_col = "signal" if "signal" in work.columns else "buy_sell"
    if side_col in work.columns:
        side = work.groupby(side_col).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).reset_index()
        st.dataframe(side, width="stretch", hide_index=True)

    st.subheader("Sector Performance")
    sector_col = "sector" if "sector" in work.columns else "industry"
    if sector_col in work.columns:
        sector = work.groupby(sector_col).agg(Trades=("pnl", "size"), Win_Rate=("pnl", lambda x: (x > 0).mean() * 100), Net_PnL=("pnl", "sum")).sort_values("Net_PnL", ascending=False).reset_index()
        st.dataframe(sector, width="stretch", hide_index=True)

    st.subheader("MAE / MFE")
    if "mae" in work.columns or "mfe" in work.columns:
        cols = [c for c in ["symbol", "entry_time", "mae", "mfe", "pnl"] if c in work.columns]
        st.dataframe(work[cols].sort_values("entry_time", ascending=False).head(50), width="stretch", hide_index=True)
    else:
        st.info("MAE/MFE columns are not yet present in historical trade records. The dashboard will display them automatically once the execution engine starts recording them; no historical values are invented.")
else:
    st.info("No closed trades yet. Signal quality and performance tables will populate after the first completed paper trades.")

if not signals.empty:
    st.subheader("Approved Signal Research")
    st.dataframe(signals.iloc[::-1].head(50), width="stretch", hide_index=True)

render_daily_footer()
