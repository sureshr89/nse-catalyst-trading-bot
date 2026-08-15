"""Plotly charts for the paper-trading dashboard."""

import pandas as pd
import plotly.express as px


def _closed(trades):
    if trades is None or trades.empty:
        return pd.DataFrame()
    df = trades.copy()
    if "status" in df.columns:
        df = df[df["status"].astype(str).str.upper() == "CLOSED"].copy()
    if "pnl" not in df.columns:
        return pd.DataFrame()
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    return df


def equity_curve(trades: pd.DataFrame):
    df = _closed(trades)
    if df.empty:
        return None
    df["equity"] = 250000 + df["pnl"].cumsum()
    return px.line(df, x=df.index, y="equity", title="Equity Curve").update_layout(template="plotly_dark", height=420)


def pnl_chart(trades: pd.DataFrame):
    df = _closed(trades)
    if df.empty:
        return None
    return px.bar(df, x=df.index, y="pnl", color="pnl", title="Trade Wise P&L").update_layout(template="plotly_dark", height=420)


def win_loss_chart(trades):
    df = _closed(trades)
    if df.empty:
        return None
    wins = int((df["pnl"] > 0).sum())
    losses = int((df["pnl"] < 0).sum())
    flat = int((df["pnl"] == 0).sum())
    return px.pie(names=["Winning", "Losing", "Flat"], values=[wins, losses, flat], title="Win vs Loss").update_layout(template="plotly_dark", height=420)


def industry_chart(trades):
    """Deprecated compatibility hook: sector/industry analysis is intentionally removed."""
    return None


def capital_chart(metrics):
    available = float(metrics.get("available_capital", 0) or 0)
    used = float(metrics.get("used_capital", 0) or 0)
    return px.pie(names=["Available", "Used"], values=[max(0.0, available), max(0.0, used)], title="Capital Utilization").update_layout(template="plotly_dark", height=420)


def monthly_pnl_chart(trades):
    df = _closed(trades)
    if df.empty or "exit_time" not in df.columns:
        return None
    df["exit_time"] = pd.to_datetime(df["exit_time"], errors="coerce")
    df = df.dropna(subset=["exit_time"])
    if df.empty:
        return None
    df["Month"] = df["exit_time"].dt.strftime("%Y-%m")
    grouped = df.groupby("Month")["pnl"].sum().reset_index()
    return px.bar(grouped, x="Month", y="pnl", title="Monthly P&L").update_layout(template="plotly_dark", height=420)
