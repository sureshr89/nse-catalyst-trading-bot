"""Read-only numerical analysis for the active NIFTY 100 paper strategy."""
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
st.caption("Read-only numerical analysis of persistent scanner signals and trade journal. No charts or graphs. This page never starts the worker or changes trading state.")


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


def prepare_trade_frame(frame):
    frame = frame.copy()
    if frame.empty:
        return frame
    for column in ["entry", "stop_loss", "target", "quantity", "pnl", "actual_risk", "risk", "reward", "rr", "position_value"]:
        numeric(frame, column)
    missing_risk = frame["risk"] <= 0
    frame.loc[missing_risk, "risk"] = (frame.loc[missing_risk, "entry"] - frame.loc[missing_risk, "stop_loss"]).abs() * frame.loc[missing_risk, "quantity"]
    missing_reward = frame["reward"] <= 0
    frame.loc[missing_reward, "reward"] = (frame.loc[missing_reward, "target"] - frame.loc[missing_reward, "entry"]).abs() * frame.loc[missing_reward, "quantity"]
    valid_risk = frame["risk"] > 0
    frame.loc[valid_risk, "rr"] = frame.loc[valid_risk, "reward"] / frame.loc[valid_risk, "risk"]
    frame["Result"] = frame["pnl"].apply(lambda value: "WIN" if value > 0 else "LOSS" if value < 0 else "FLAT")
    return frame


def outcome_stats(frame, label):
    if frame.empty:
        return {"Category": label, "Trades": 0, "Wins": 0, "Losses": 0, "Flat": 0, "Win %": 0.0, "Total P&L": 0.0, "Avg P&L": 0.0, "Avg Risk": 0.0, "Avg R:R": 0.0, "Profit Factor": 0.0}
    pnl = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    wins = int((pnl > 0).sum())
    losses = int((pnl < 0).sum())
    flat = int((pnl == 0).sum())
    gross_profit = float(pnl[pnl > 0].sum())
    gross_loss = abs(float(pnl[pnl < 0].sum()))
    return {
        "Category": label,
        "Trades": len(frame),
        "Wins": wins,
        "Losses": losses,
        "Flat": flat,
        "Win %": round(wins / len(frame) * 100, 2),
        "Total P&L": round(float(pnl.sum()), 2),
        "Avg P&L": round(float(pnl.mean()), 2),
        "Avg Risk": round(float(frame["risk"].mean()), 2),
        "Avg R:R": round(float(frame["rr"].mean()), 3),
        "Profit Factor": round(gross_profit / gross_loss, 3) if gross_loss else 0.0,
    }


def group_analysis(frame, group_column):
    if frame.empty or group_column not in frame.columns:
        return pd.DataFrame()
    rows = []
    for value, group in frame.groupby(group_column, dropna=False):
        rows.append(outcome_stats(group, str(value) if str(value) else "UNKNOWN"))
    return pd.DataFrame(rows).sort_values(["Total P&L", "Trades"], ascending=[False, False]) if rows else pd.DataFrame()


trades = load_csv(TRADES_FILE)
signals = load_csv(SIGNALS_FILE)
state = load_state()

actual = pd.DataFrame()
missed = pd.DataFrame()
if not trades.empty and "status" in trades.columns:
    statuses = trades["status"].astype(str).str.upper()
    actual = trades[statuses == "CLOSED"].copy()
    missed = trades[statuses.isin(["MISSED_CAPITAL_OPEN", "MISSED_CAPITAL_CLOSED"])].copy()

actual = prepare_trade_frame(actual)
missed_closed = prepare_trade_frame(missed[missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_CLOSED"].copy()) if not missed.empty else pd.DataFrame()

# ------------------------- ACTUAL TRADES -------------------------
st.header("1. Actual Trades Taken")
if actual.empty:
    st.info("No closed actual trades are available yet.")
else:
    stats = outcome_stats(actual, "Actual trades")
    a, b, c, d, e = st.columns(5)
    a.metric("Closed Trades", stats["Trades"])
    b.metric("Win Rate", f'{stats["Win %"]:.2f}%')
    c.metric("Total P&L", f'₹{stats["Total P&L"]:,.2f}')
    d.metric("Avg P&L", f'₹{stats["Avg P&L"]:,.2f}')
    e.metric("Profit Factor", f'{stats["Profit Factor"]:.3f}')

    st.subheader("Actual Performance Summary")
    st.dataframe(pd.DataFrame([stats]), use_container_width=True, hide_index=True)

    st.subheader("Actual Outcome by Side")
    side_table = group_analysis(actual, "signal")
    st.dataframe(side_table, use_container_width=True, hide_index=True) if not side_table.empty else st.info("No side-level data available.")

    st.subheader("Actual Outcome by Exit Reason")
    exit_table = group_analysis(actual, "exit_reason")
    st.dataframe(exit_table, use_container_width=True, hide_index=True) if not exit_table.empty else st.info("No exit-reason data available.")

    st.subheader("Actual Outcome by Stock")
    stock_table = group_analysis(actual, "symbol")
    st.dataframe(stock_table, use_container_width=True, hide_index=True) if not stock_table.empty else st.info("No stock-level data available.")

    st.subheader("Actual Trade Details")
    preferred = ["trade_id", "symbol", "signal", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "exit_reason", "entry_time", "exit_time", "status"]
    columns = [column for column in preferred if column in actual.columns]
    st.dataframe(actual[columns].sort_values("exit_time", ascending=False, na_position="last"), use_container_width=True, hide_index=True)

# ------------------- MISSED DUE TO CAPITAL ----------------------
st.header("2. Qualified Trades Missed Due to Capital")
if missed.empty:
    st.info("No qualified trades have been missed because of insufficient capital yet.")
else:
    open_missed = missed[missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_OPEN"].copy()
    resolved = len(missed_closed)
    stats = outcome_stats(missed_closed, "Capital-missed resolved")
    st.subheader("Capital-Missed Summary")
    st.dataframe(pd.DataFrame([{
        "Qualified but blocked": len(missed),
        "Still being tracked": len(open_missed),
        "Resolved": resolved,
        "Wins": stats["Wins"],
        "Losses": stats["Losses"],
        "Flat": stats["Flat"],
        "Hypothetical Win %": stats["Win %"],
        "Hypothetical P&L": stats["Total P&L"],
        "Average Hypothetical P&L": stats["Avg P&L"],
        "Profit Factor": stats["Profit Factor"],
    }]), use_container_width=True, hide_index=True)

    if not missed_closed.empty:
        st.subheader("Capital-Missed Outcome by Side")
        side_table = group_analysis(missed_closed, "signal")
        st.dataframe(side_table, use_container_width=True, hide_index=True)

        st.subheader("Capital-Missed Outcome by Exit Reason")
        exit_table = group_analysis(missed_closed, "exit_reason")
        st.dataframe(exit_table, use_container_width=True, hide_index=True)

    st.subheader("All Capital-Missed Opportunities")
    preferred = ["trade_id", "symbol", "signal", "entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "exit_reason", "entry_time", "exit_time", "status"]
    columns = [column for column in preferred if column in missed.columns]
    st.dataframe(missed[columns].sort_values("entry_time", ascending=False, na_position="last"), use_container_width=True, hide_index=True)

# --------------------- STRATEGY CAPABILITY ----------------------
st.header("3. Strategy Capability — Actual vs Capital-Missed")
actual_stats = outcome_stats(actual, "Actual trades")
missed_stats = outcome_stats(missed_closed, "Qualified but missed due to capital")
comparison = pd.DataFrame([actual_stats, missed_stats])
st.dataframe(comparison, use_container_width=True, hide_index=True)

if not actual.empty or not missed_closed.empty:
    actual_total = float(actual["pnl"].sum()) if not actual.empty else 0.0
    missed_total = float(missed_closed["pnl"].sum()) if not missed_closed.empty else 0.0
    combined_count = len(actual) + len(missed_closed)
    combined_wins = int((actual["pnl"] > 0).sum()) + int((missed_closed["pnl"] > 0).sum())
    st.subheader("Capability Interpretation")
    st.dataframe(pd.DataFrame([{
        "Actual realized P&L": round(actual_total, 2),
        "Missed hypothetical P&L": round(missed_total, 2),
        "Combined qualified outcomes": combined_count,
        "Combined wins": combined_wins,
        "Combined win %": round(combined_wins / combined_count * 100, 2) if combined_count else 0.0,
        "Open capital-missed opportunities": int((missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_OPEN").sum()) if not missed.empty else 0,
    }]), use_container_width=True, hide_index=True)
    st.caption("Missed-capital results are hypothetical and are never included in actual P&L.")

# --------------------- SCANNER SIGNAL ANALYSIS -------------------
st.header("4. Scanner Signal Analysis")
if signals.empty:
    st.info("No scanner signals have been recorded yet.")
else:
    sig = signals.copy()
    for column in ["entry", "stop_loss", "target", "risk_reward", "risk_per_share", "actual_risk", "position_value"]:
        numeric(sig, column)
    approved_series = sig["approved"].astype(str).str.upper().isin(["TRUE", "1", "YES"]) if "approved" in sig.columns else pd.Series(False, index=sig.index)
    st.dataframe(pd.DataFrame([{
        "Recorded unique signals": len(sig),
        "Risk approved": int(approved_series.sum()),
        "Risk rejected": int((~approved_series).sum()),
        "Approval %": round(approved_series.mean() * 100, 2) if len(sig) else 0.0,
    }]), use_container_width=True, hide_index=True)

    if "reason" in sig.columns:
        reasons = sig.assign(_reason=sig["reason"].fillna("").astype(str)).groupby("_reason", dropna=False).size().reset_index(name="Count").rename(columns={"_reason": "Reason"}).sort_values("Count", ascending=False)
        st.subheader("Signal Approval / Rejection Reasons")
        st.dataframe(reasons, use_container_width=True, hide_index=True)

    preferred = [
        "timestamp", "symbol", "signal", "entry", "stop_loss", "target", "risk_reward", "risk_per_share",
        "actual_risk", "position_value", "pdc", "today_open", "today_low", "today_high", "nifty100_direction",
        "sector", "sector_direction", "stock_today_direction", "previous_day_direction", "setup_type",
        "entry_candle_open", "entry_candle_close", "approved", "reason",
    ]
    columns = [column for column in preferred if column in sig.columns]
    st.subheader("Unique Scanner Signal Records")
    st.dataframe(sig[columns].iloc[::-1], use_container_width=True, hide_index=True)

st.divider()
st.caption("Analysis is read-only. Execution remains in main.py through the persistent bot worker. No charts or graphs are used.")
