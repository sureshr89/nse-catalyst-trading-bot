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

# Split the persistent journal into real executed trades and qualified trades
# that were blocked specifically because available capital was insufficient.
actual = trades.copy()
missed = trades.copy()
if not trades.empty and "status" in trades.columns:
    statuses = trades["status"].astype(str).str.upper()
    actual = trades[statuses == "CLOSED"].copy()
    missed = trades[statuses.isin(["MISSED_CAPITAL_OPEN", "MISSED_CAPITAL_CLOSED"])].copy()
else:
    actual = pd.DataFrame()
    missed = pd.DataFrame()

# Resolve any remaining capital-missed positions at the latest available state
# only through the tracker; this page itself remains read-only.
missed_closed = missed[missed.get("status", pd.Series(dtype=str)).astype(str).str.upper().eq("MISSED_CAPITAL_CLOSED")].copy() if not missed.empty else pd.DataFrame()


def prepare_trade_frame(frame):
    frame = frame.copy()
    if frame.empty:
        return frame
    for column in ["entry", "stop_loss", "target", "quantity", "pnl", "actual_risk", "risk", "reward", "rr"]:
        numeric(frame, column)
    missing_risk = frame["risk"] <= 0
    frame.loc[missing_risk, "risk"] = (frame.loc[missing_risk, "entry"] - frame.loc[missing_risk, "stop_loss"]).abs() * frame.loc[missing_risk, "quantity"]
    missing_reward = frame["reward"] <= 0
    frame.loc[missing_reward, "reward"] = (frame.loc[missing_reward, "target"] - frame.loc[missing_reward, "entry"]).abs() * frame.loc[missing_reward, "quantity"]
    valid_risk = frame["risk"] > 0
    frame.loc[valid_risk, "rr"] = frame.loc[valid_risk, "reward"] / frame.loc[valid_risk, "risk"]
    if "symbol" not in frame.columns:
        frame["symbol"] = "UNKNOWN"
    frame["symbol"] = frame["symbol"].fillna("UNKNOWN").astype(str)
    if "signal" not in frame.columns:
        frame["signal"] = "UNKNOWN"
    frame["signal"] = frame["signal"].fillna("UNKNOWN").astype(str).str.upper()
    frame["Result"] = frame["pnl"].apply(lambda value: "Win" if value > 0 else "Loss" if value < 0 else "Flat")
    return frame


actual = prepare_trade_frame(actual)
missed_closed = prepare_trade_frame(missed_closed)

# ------------------------- ACTUAL TRADES -------------------------
st.header("1. Actual Trades Taken")
if not actual.empty:
    total = len(actual)
    wins = int((actual["pnl"] > 0).sum())
    losses = int((actual["pnl"] < 0).sum())
    flat = int((actual["pnl"] == 0).sum())
    pnl = float(actual["pnl"].sum())
    win_rate = wins / total * 100.0 if total else 0.0
    gross_profit = float(actual.loc[actual["pnl"] > 0, "pnl"].sum())
    gross_loss = abs(float(actual.loc[actual["pnl"] < 0, "pnl"].sum()))
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

    st.subheader("Actual Trade Win/Loss")
    st.bar_chart(pd.DataFrame({"Trades": [wins, losses, flat]}, index=["Win", "Loss", "Flat"]), use_container_width=True)

    st.subheader("Actual P&L")
    st.bar_chart(actual.groupby("symbol")["pnl"].sum().sort_values(ascending=False), use_container_width=True)

    st.subheader("Actual Cumulative P&L")
    pnl_series = actual.copy()
    time_col = next((column for column in ["exit_time", "entry_time"] if column in pnl_series.columns), None)
    if time_col:
        pnl_series["_time"] = pd.to_datetime(pnl_series[time_col], errors="coerce")
        if pnl_series["_time"].notna().any():
            pnl_series = pnl_series.sort_values("_time", na_position="last")
    pnl_series.index = range(1, len(pnl_series) + 1)
    st.line_chart(pnl_series["pnl"].cumsum(), use_container_width=True)

    st.subheader("Actual Trade Details")
    preferred = ["symbol", "signal", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "exit_reason", "entry_time", "exit_time", "status"]
    columns = [column for column in preferred if column in actual.columns]
    st.dataframe(actual[columns].iloc[::-1], use_container_width=True, hide_index=True)
else:
    st.info("No closed actual trades are available yet.")

# ------------------- MISSED DUE TO CAPITAL ----------------------
st.header("2. Qualified Trades Missed Due to Capital")
if not missed.empty:
    open_missed = missed[missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_OPEN"].copy()
    closed_missed = missed_closed.copy()
    resolved = len(closed_missed)
    mwins = int((closed_missed["pnl"] > 0).sum()) if not closed_missed.empty else 0
    mlosses = int((closed_missed["pnl"] < 0).sum()) if not closed_missed.empty else 0
    mflat = int((closed_missed["pnl"] == 0).sum()) if not closed_missed.empty else 0
    hypothetical_pnl = float(closed_missed["pnl"].sum()) if not closed_missed.empty else 0.0
    mwin_rate = mwins / resolved * 100.0 if resolved else 0.0

    a, b, c, d, e = st.columns(5)
    a.metric("Missed Due to Capital", len(missed))
    b.metric("Resolved", resolved)
    c.metric("Hypothetical Wins", mwins)
    d.metric("Hypothetical Losses", mlosses)
    e.metric("Hypothetical Win Rate", f"{mwin_rate:.1f}%")
    st.metric("Hypothetical P&L", f"₹{hypothetical_pnl:,.2f}")
    st.caption(f"Currently being tracked: {len(open_missed)} capital-blocked opportunities still open.")

    if resolved:
        st.subheader("Missed Trade Win/Loss")
        st.bar_chart(pd.DataFrame({"Trades": [mwins, mlosses, mflat]}, index=["Win", "Loss", "Flat"]), use_container_width=True)

        st.subheader("Missed Trade Cumulative Hypothetical P&L")
        mp = closed_missed.copy()
        time_col = next((column for column in ["exit_time", "entry_time"] if column in mp.columns), None)
        if time_col:
            mp["_time"] = pd.to_datetime(mp[time_col], errors="coerce")
            if mp["_time"].notna().any():
                mp = mp.sort_values("_time", na_position="last")
        mp.index = range(1, len(mp) + 1)
        st.line_chart(mp["pnl"].cumsum(), use_container_width=True)

    st.subheader("Capital-Missed Trade Details")
    preferred = ["symbol", "signal", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "exit_reason", "entry_time", "exit_time", "status"]
    columns = [column for column in preferred if column in missed.columns]
    st.dataframe(missed[columns].iloc[::-1], use_container_width=True, hide_index=True)
else:
    st.info("No qualified trades have been missed because of insufficient capital yet.")

st.divider()

# --------------------- SCANNER SIGNAL ANALYSIS -------------------
st.header("3. Scanner Signal Analysis")
if signals.empty:
    st.info("No scanner signals have been recorded yet.")
else:
    sig = signals.copy()
    for column in ["entry", "stop_loss", "target", "risk_reward", "risk_per_share", "actual_risk", "position_value"]:
        numeric(sig, column)
    approved_series = sig["approved"].astype(str).str.upper().eq("TRUE") if "approved" in sig.columns else pd.Series(False, index=sig.index)
    a, b, c = st.columns(3)
    a.metric("Recorded Signals", len(sig))
    b.metric("Risk Approved", int(approved_series.sum()))
    c.metric("Rejected", int((~approved_series).sum()))
    preferred = [
        "timestamp", "symbol", "signal", "entry", "stop_loss", "target", "risk_reward", "risk_per_share",
        "actual_risk", "position_value", "pdc", "today_open", "today_low", "today_high", "nifty100_direction",
        "sector", "sector_direction", "stock_today_direction", "previous_day_direction", "setup_type",
        "entry_candle_open", "entry_candle_close", "approved", "reason",
    ]
    columns = [column for column in preferred if column in sig.columns]
    st.dataframe(sig[columns].iloc[::-1], use_container_width=True, hide_index=True)

st.divider()
st.caption("Analysis is read-only. Execution remains in main.py through the persistent bot worker.")
