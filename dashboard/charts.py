"""
Plotly charts for the Trading Dashboard
"""

import pandas as pd
import plotly.express as px


# ============================================================
# EQUITY CURVE
# ============================================================

def equity_curve(trades: pd.DataFrame):

    if trades.empty:
        return None

    df = trades.copy()

    df["equity"] = 250000 + df["pnl"].cumsum()

    fig = px.line(
        df,
        x=df.index,
        y="equity",
        title="Equity Curve"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig


# ============================================================
# TRADE PNL
# ============================================================

def pnl_chart(trades: pd.DataFrame):

    if trades.empty:
        return None

    fig = px.bar(
        trades,
        x=trades.index,
        y="pnl",
        color="pnl",
        title="Trade Wise P&L"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig


# ============================================================
# WIN / LOSS PIE
# ============================================================

def win_loss_chart(trades):

    if trades.empty:
        return None

    wins = len(
        trades[
            trades["pnl"] > 0
        ]
    )

    losses = len(
        trades[
            trades["pnl"] < 0
        ]
    )

    fig = px.pie(
        names=["Winning", "Losing"],
        values=[wins, losses],
        title="Win vs Loss"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig


# ============================================================
# INDUSTRY PERFORMANCE
# ============================================================

def industry_chart(trades):

    if trades.empty:
        return None

    if "industry" not in trades.columns:
        return None

    df = (
        trades
        .groupby("industry")["pnl"]
        .sum()
        .reset_index()
    )

    fig = px.bar(
        df,
        x="industry",
        y="pnl",
        title="Industry Performance"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig


# ============================================================
# CAPITAL UTILIZATION
# ============================================================

def capital_chart(metrics):

    fig = px.pie(
        names=[
            "Available",
            "Used"
        ],
        values=[
            metrics["available_capital"],
            metrics["used_capital"]
        ],
        title="Capital Utilization"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig


# ============================================================
# MONTHLY PNL
# ============================================================

def monthly_pnl_chart(trades):

    if trades.empty:
        return None

    if "exit_time" not in trades.columns:
        return None

    df = trades.copy()

    df["exit_time"] = pd.to_datetime(
        df["exit_time"],
        errors="coerce"
    )

    df["Month"] = (
        df["exit_time"]
        .dt.strftime("%Y-%m")
    )

    df = (
        df.groupby("Month")["pnl"]
        .sum()
        .reset_index()
    )

    fig = px.bar(
        df,
        x="Month",
        y="pnl",
        title="Monthly P&L"
    )

    fig.update_layout(
        template="plotly_dark",
        height=420
    )

    return fig