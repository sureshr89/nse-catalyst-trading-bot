"""
Dashboard Utility Functions
"""

import pandas as pd
import os


# ============================================================
# LOAD CSV
# ============================================================

def load_csv(path):

    if not os.path.exists(path):
        return pd.DataFrame()

    try:

        return pd.read_csv(path)

    except Exception:

        return pd.DataFrame()


# ============================================================
# FORMAT RUPEE
# ============================================================

def format_money(value):

    try:

        return f"₹{value:,.2f}"

    except Exception:

        return "₹0.00"


# ============================================================
# FORMAT PERCENTAGE
# ============================================================

def format_percent(value):

    try:

        return f"{value:.2f}%"

    except Exception:

        return "0.00%"


# ============================================================
# GREEN / RED COLOR
# ============================================================

def pnl_color(value):

    if value > 0:
        return "green"

    elif value < 0:
        return "red"

    return "white"


# ============================================================
# OPEN POSITIONS
# ============================================================

def open_positions(trades):

    if trades.empty:
        return pd.DataFrame()

    if "status" not in trades.columns:
        return pd.DataFrame()

    return trades[
        trades["status"] == "OPEN"
    ]


# ============================================================
# CLOSED POSITIONS
# ============================================================

def closed_positions(trades):

    if trades.empty:
        return pd.DataFrame()

    if "status" not in trades.columns:
        return pd.DataFrame()

    return trades[
        trades["status"] == "CLOSED"
    ]


# ============================================================
# WINNING TRADES
# ============================================================

def winning_trades(trades):

    if trades.empty:
        return pd.DataFrame()

    return trades[
        trades["pnl"] > 0
    ]


# ============================================================
# LOSING TRADES
# ============================================================

def losing_trades(trades):

    if trades.empty:
        return pd.DataFrame()

    return trades[
        trades["pnl"] < 0
    ]


# ============================================================
# LAST N TRADES
# ============================================================

def last_trades(trades, n=10):

    if trades.empty:
        return pd.DataFrame()

    return trades.tail(n)


# ============================================================
# TODAY'S PNL
# ============================================================

def todays_pnl(trades):

    if trades.empty:
        return 0.0

    return float(
        trades["pnl"].sum()
    )


# ============================================================
# AUTO REFRESH
# ============================================================

REFRESH_SECONDS = 5