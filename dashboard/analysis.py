"""Read-only trading analysis for the active NIFTY 100 strategy."""
from pathlib import Path
import json

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
SIGNALS_FILE = PROJECT_ROOT / "outputs" / "signals.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"

st.set_page_config(page_title="NSE Catalyst - Analysis", page_icon="📊", layout="wide")
st.title("📊 Trading Analysis")
st.caption("Read-only analysis of persistent scanner signals and trade journal. This page never starts the worker or changes trading state.")


def load_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def numeric(frame, column, default=0.0):
    if column not in frame.columns:
        frame[column] = default
    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(default)


trades = load_csv(TRADES_FILE)
signals = load_csv(SIGNALS_FILE)
state = load_state()

if not trades.empty:
    closed = trades.copy()
    if "status" in closed.columns:
        closed = closed[closed["status"].astype(str).str.upper() == "CLOSED"].copy()
else:
    closed = pd.DataFrame()

if not closed.empty:
    for column in ["entry", "stop_loss", "target", "quantity", "pnl", "actual_risk", "risk", "reward", "rr"]:
        numeric(closed, column)

    missing_risk = closed["risk"] <= 0
    closed.loc[missing_risk, "risk"] = (closed.loc[missing_risk, "entry"] - closed.loc[missing_risk, "stop_loss"]).abs()
    missing_reward = closed["reward"] <= 0
    closed.loc[missing_reward, "reward"] = (closed.loc[missing_reward, "target"] - closed.loc[missing_reward, "entry"]).abs()
    valid_risk = closed["risk"] > 0
    closed.loc[valid_risk, "rr"] = closed.loc[valid_risk, "reward"] / closed.loc[valid_risk, "risk"]

    if "symbol" not in closed.columns:
        closed["symbol"] = "UNKNOWN"
    closed["symbol"] = closed["symbol"].fillna("UNKNOWN").astype(str)
    if "signal" not in closed.columns:
        closed["signal"] = "UNKNOWN"
    closed["signal"] = closed["signal"].fillna("UNKNOWN").astype(str).str.upper()

    total = len(closed)
    wins = int((closed["pnl"] > 0).sum())
    losses = int((closed["pnl"] < 0).sum())
    flat = int((closed["pnl"] == 0).sum())
    pnl = float(closed["pnl"].sum())
    win_rate = wins / total * 100.0 if total else 0.0
    gross_profit = float(closed.loc[closed["pnl"] > 0, "pnl"].sum())
    gross_loss = abs(float(closed.loc[closed["pnl"] < 0, "pnl"].sum()))
    profit_factor = gross_profit / gross_loss if gross_loss else 0.0
    open_count = len(state.get("open_positions", {}) or {})

    a, b, c, d, e, f = st.columns(6)
    a.metric("Closed Trades", total)
    b.metric("Wins", wins)
    c.metric("Losses", losses)
    d.metric("Win Rate", f"{win_rate:.1f}%")
    e.metric("Profit Factor", f"{profit_factor:.2f}")
    f.metric("Open Positions", open_count)
    st.metric("Realized P&L", f"₹{pnl:,.2f}")

    st.subheader("1. Win vs Loss")
    st.bar_chart(pd.DataFrame({"Trades": [wins, losses]}, index=["Win", "Loss"]), use_container_width=True)

    st.subheader("2. Stock-wise Win/Loss")
    stock_result = closed.assign(
        Result=closed["pnl"].apply(lambda value: "Win" if value > 0 else "Loss" if value < 0 else "Flat")
    )
    stock_wl = pd.crosstab(stock_result["symbol"], stock_result["Result"])
    for column in ["Win", "Loss", "Flat"]:
        if column not in stock_wl.columns:
            stock_wl[column] = 0
    stock_wl = stock_wl[["Win", "Loss", "Flat"]]
    st.bar_chart(stock_wl, use_container_width=True)

    st.subheader("3. P&L by Stock")
    stock_pnl = closed.groupby("symbol")["pnl"].sum().sort_values(ascending=False)
    st.bar_chart(stock_pnl, use_container_width=True)

    st.subheader("4. Trades by Stock")
    trades_by_stock = closed["symbol"].value_counts().sort_values(ascending=False)
    st.bar_chart(trades_by_stock, use_container_width=True)

    st.subheader("5. Cumulative P&L")
    pnl_series = closed.copy()
    time_col = next((column for column in ["exit_time", "entry_time"] if column in pnl_series.columns), None)
    if time_col:
        pnl_series["_time"] = pd.to_datetime(pnl_series[time_col], errors="coerce")
        if pnl_series["_time"].notna().any():
            pnl_series = pnl_series.sort_values("_time", na_position="last")
    pnl_series.index = range(1, len(pnl_series) + 1)
    st.line_chart(pnl_series["pnl"].cumsum(), use_container_width=True)

    st.subheader("6. Risk / Reward")
    rr_plot = pnl_series[["risk", "reward"]].copy()
    rr_plot.index = [f"Trade {index}" for index in range(1, len(rr_plot) + 1)]
    st.line_chart(rr_plot, use_container_width=True)
    valid_rr = pnl_series["rr"].replace([float("inf"), -float("inf")], pd.NA).dropna()
    avg_rr = float(valid_rr.mean()) if not valid_rr.empty else 0.0
    st.caption(f"Average recorded R:R: {avg_rr:.2f}. Strategy minimum: 1:1.5.")

    st.subheader("7. Exit Reason")
    if "exit_reason" in closed.columns:
        st.bar_chart(closed["exit_reason"].fillna("UNKNOWN").astype(str).value_counts(), use_container_width=True)

    st.subheader("8. BUY vs SELL")
    side_counts = pd.crosstab(stock_result["signal"], stock_result["Result"])
    for column in ["Win", "Loss", "Flat"]:
        if column not in side_counts.columns:
            side_counts[column] = 0
    st.bar_chart(side_counts[["Win", "Loss", "Flat"]], use_container_width=True)

    st.subheader("9. Sector Performance")
    sector_col = "sector" if "sector" in closed.columns else "industry" if "industry" in closed.columns else None
    if sector_col:
        st.bar_chart(closed.groupby(sector_col)["pnl"].sum().sort_values(ascending=False), use_container_width=True)

    st.subheader("10. Setup Quality")
    quality_cols = [column for column in [
        "symbol", "signal", "pnl", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr",
        "pdc", "today_open", "today_low", "today_high", "nifty100_direction", "sector", "sector_direction",
        "stock_today_direction", "previous_day_direction", "setup_type", "exit_reason", "status",
    ] if column in closed.columns]
    st.dataframe(closed[quality_cols].iloc[::-1], use_container_width=True, hide_index=True)
else:
    st.info("No closed trades are available for analysis yet.")

st.divider()
st.header("📡 Scanner Signal Analysis")
if signals.empty:
    st.info("No scanner signals have been recorded yet.")
else:
    sig = signals.copy()
    for column in ["entry", "stop_loss", "target", "risk_reward", "actual_risk"]:
        numeric(sig, column)
    approved_series = sig["approved"].astype(str).str.upper().eq("TRUE") if "approved" in sig.columns else pd.Series(False, index=sig.index)
    a, b, c = st.columns(3)
    a.metric("Recorded Signals", len(sig))
    b.metric("Risk Approved", int(approved_series.sum()))
    c.metric("Rejected", int((~approved_series).sum()))
    preferred = [
        "timestamp", "symbol", "signal", "entry", "stop_loss", "target", "risk_reward", "actual_risk",
        "pdc", "today_open", "today_low", "today_high", "nifty100_direction", "sector", "sector_direction",
        "stock_today_direction", "previous_day_direction", "setup_type", "approved", "reason",
    ]
    columns = [column for column in preferred if column in sig.columns]
    st.dataframe(sig[columns].iloc[::-1], use_container_width=True, hide_index=True)

st.divider()
st.caption("Analysis is read-only. Execution remains in main.py through the persistent bot worker.")
