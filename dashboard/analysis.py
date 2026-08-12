"""Read-only trading analysis page.

This page only reads persistent trade data. It never starts the worker,
places trades, changes trading state, or writes files.
"""
from pathlib import Path
import json

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"

st.set_page_config(
    page_title="NSE Catalyst - Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Trading Analysis")
st.caption("Read-only analysis page — no trading logic, worker, or state is changed here.")


def load_trades():
    if not TRADES_FILE.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(TRADES_FILE)
    except Exception:
        return pd.DataFrame()


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def numeric_column(frame, name, default=0.0):
    if name not in frame.columns:
        frame[name] = default
    frame[name] = pd.to_numeric(frame[name], errors="coerce").fillna(default)
    return frame


trades = load_trades()
state = load_state()

if trades.empty:
    st.info("No persistent trade journal data is available yet.")
else:
    closed = trades.copy()
    if "status" in closed.columns:
        closed = closed[closed["status"].astype(str).str.upper() == "CLOSED"].copy()

    if closed.empty:
        st.info("No closed trades are available for analysis yet.")
    else:
        # Normalize fields used by the read-only charts.
        numeric_column(closed, "pnl")
        numeric_column(closed, "risk")
        numeric_column(closed, "reward")
        numeric_column(closed, "rr")

        if "stock" not in closed.columns:
            closed["stock"] = "UNKNOWN"
        closed["stock"] = closed["stock"].fillna("UNKNOWN").astype(str)

        total = len(closed)
        wins = int((closed["pnl"] > 0).sum())
        losses = int((closed["pnl"] < 0).sum())
        pnl = float(closed["pnl"].sum())
        win_rate = (wins / total * 100.0) if total else 0.0
        open_count = len(state.get("open_positions", {}) or {})

        a, b, c, d, e = st.columns(5)
        a.metric("Closed Trades", total)
        b.metric("Winning Trades", wins)
        c.metric("Losing Trades", losses)
        d.metric("Win Rate", f"{win_rate:.1f}%")
        e.metric("Open Positions", open_count)
        st.metric("Realized P&L", f"₹{pnl:,.2f}")

        # ------------------------------------------------------------
        # 10. WIN VS LOSS
        # ------------------------------------------------------------
        st.subheader("10. Win vs Loss")
        win_loss = pd.DataFrame({"Trades": [wins, losses]}, index=["Win", "Loss"])
        st.bar_chart(win_loss, y="Trades", use_container_width=True)

        # ------------------------------------------------------------
        # 11. STOCK-WISE WIN / LOSS
        # ------------------------------------------------------------
        st.subheader("11. Stock-wise Win / Loss")
        stock_win_loss = closed.assign(
            Result=closed["pnl"].apply(lambda x: "Win" if x > 0 else ("Loss" if x < 0 else "Flat"))
        )
        stock_counts = pd.crosstab(stock_win_loss["stock"], stock_win_loss["Result"])
        for col in ["Win", "Loss"]:
            if col not in stock_counts.columns:
                stock_counts[col] = 0
        stock_counts = stock_counts[["Win", "Loss"]].sort_values(["Win", "Loss"], ascending=False)
        st.bar_chart(stock_counts, use_container_width=True)

        # ------------------------------------------------------------
        # 12. P&L BY STOCK
        # ------------------------------------------------------------
        st.subheader("12. P&L by Stock")
        pnl_by_stock = closed.groupby("stock", dropna=False)["pnl"].sum().sort_values(ascending=False)
        st.bar_chart(pnl_by_stock, use_container_width=True)

        # ------------------------------------------------------------
        # 13. TRADES BY STOCK
        # ------------------------------------------------------------
        st.subheader("13. Trades by Stock")
        trades_by_stock = closed["stock"].value_counts().sort_values(ascending=False)
        st.bar_chart(trades_by_stock, use_container_width=True)

        # ------------------------------------------------------------
        # 14. CUMULATIVE P&L
        # ------------------------------------------------------------
        st.subheader("14. Cumulative P&L")
        cumulative = closed.copy()
        time_col = next(
            (col for col in ["exit_time", "entry_time", "timestamp", "date"] if col in cumulative.columns),
            None,
        )
        if time_col:
            cumulative["_analysis_time"] = pd.to_datetime(cumulative[time_col], errors="coerce")
            if cumulative["_analysis_time"].notna().any():
                cumulative = cumulative.sort_values("_analysis_time", na_position="last")
        cumulative["Cumulative P&L"] = cumulative["pnl"].cumsum()
        cumulative.index = range(1, len(cumulative) + 1)
        st.line_chart(cumulative["Cumulative P&L"], use_container_width=True)

        # ------------------------------------------------------------
        # 15. RISK / REWARD
        # ------------------------------------------------------------
        st.subheader("15. Risk / Reward")
        rr_frame = closed[["stock", "risk", "reward", "rr"]].copy()
        rr_frame["Trade"] = [f"Trade {i}" for i in range(1, len(rr_frame) + 1)]
        rr_frame = rr_frame.set_index("Trade")
        st.line_chart(rr_frame[["risk", "reward"]], use_container_width=True)

        avg_rr = float(closed["rr"].replace([float("inf"), -float("inf")], pd.NA).dropna().mean()) if not closed["rr"].dropna().empty else 0.0
        st.caption(f"Average recorded R:R: {avg_rr:.2f} | R:R values are read directly from the persistent trade journal.")

        st.divider()
        st.subheader("Trade Details")
        st.dataframe(closed, use_container_width=True, hide_index=True)

st.divider()
st.caption("Analysis is read-only. Trade execution and persistence remain on the main trading dashboard/worker.")
