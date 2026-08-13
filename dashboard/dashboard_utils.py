"""Dashboard utility functions for the paper-trading journal."""

import os

import pandas as pd


def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def format_money(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "₹0.00"


def format_percent(value):
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "0.00%"


def pnl_color(value):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    if value > 0:
        return "green"
    if value < 0:
        return "red"
    return "white"


def open_positions(trades):
    if trades is None or trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    return trades[trades["status"].astype(str).str.upper() == "OPEN"].copy()


def closed_positions(trades):
    if trades is None or trades.empty or "status" not in trades.columns:
        return pd.DataFrame()
    return trades[trades["status"].astype(str).str.upper() == "CLOSED"].copy()


def winning_trades(trades):
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return pd.DataFrame()
    frame = trades.copy()
    if "status" in frame.columns:
        frame = frame[frame["status"].astype(str).str.upper() == "CLOSED"]
    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce")
    return frame[frame["pnl"] > 0].copy()


def losing_trades(trades):
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return pd.DataFrame()
    frame = trades.copy()
    if "status" in frame.columns:
        frame = frame[frame["status"].astype(str).str.upper() == "CLOSED"]
    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce")
    return frame[frame["pnl"] < 0].copy()


def last_trades(trades, n=10):
    if trades is None or trades.empty:
        return pd.DataFrame()
    return trades.tail(max(0, int(n))).copy()


def todays_pnl(trades, date=None):
    """Return realized P&L for one IST calendar date; default is today."""
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return 0.0

    frame = trades.copy()
    if "status" in frame.columns:
        frame = frame[frame["status"].astype(str).str.upper() == "CLOSED"].copy()
    if frame.empty:
        return 0.0

    time_col = "exit_time" if "exit_time" in frame.columns else "entry_time" if "entry_time" in frame.columns else None
    if time_col is None:
        return 0.0

    timestamps = pd.to_datetime(frame[time_col], errors="coerce")
    if timestamps.dt.tz is None:
        dates = timestamps.dt.date
    else:
        dates = timestamps.dt.tz_convert("Asia/Kolkata").dt.date

    target_date = pd.Timestamp(date).date() if date is not None else pd.Timestamp.now(tz="Asia/Kolkata").date()
    pnl = pd.to_numeric(frame.loc[dates == target_date, "pnl"], errors="coerce").fillna(0.0)
    return float(pnl.sum())


REFRESH_SECONDS = 5
