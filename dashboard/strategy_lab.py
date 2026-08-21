"""Unified S1-S5 comparison and signal analytics.

The labels and rules below are synchronized with the executable strategy
contract in strategy.nifty500_price_action_strategies.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"

STRATEGIES = {
    "S1": "PDH/PDL Sweep + Open Reclaim",
    "S2": "PDH/PDL Breakout + Retest",
    "S3": "Opposite PDH/PDL Sweep + Open Reversal",
    "S4": "Intraday High/Low Breakout",
    "S5": "Direct PDH/PDL Breakout",
}


def _read(name):
    path = OUTPUTS / name
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _strategy_col(df):
    if df.empty:
        return None
    for column in df.columns:
        normalized = str(column).lower().replace(" ", "_")
        if normalized in {"strategy", "strategy_id", "setup", "system"}:
            return column
    return None


def _stats():
    trades = _read("trades.csv")
    signals = _read("signals.csv")
    tc = _strategy_col(trades)
    sc = _strategy_col(signals)
    rows = []

    for sid in STRATEGIES:
        t = trades[trades[tc].astype(str).str.upper().str.startswith(sid)] if tc else pd.DataFrame()
        s = signals[signals[sc].astype(str).str.upper().str.startswith(sid)] if sc else pd.DataFrame()
        rcol = next((c for c in t.columns if str(c).lower() in {"r", "r_multiple", "net_r", "pnl_r"}), None)
        pcol = next((c for c in t.columns if str(c).lower() in {"pnl", "p&l", "profit_loss", "net_pnl"}), None)
        vals = pd.to_numeric(t[rcol], errors="coerce").dropna() if rcol else pd.Series(dtype=float)
        wins = int((vals > 0).sum()) if not vals.empty else 0
        losses = int((vals < 0).sum()) if not vals.empty else 0
        rows.append({
            "Strategy": sid,
            "Signals": len(s),
            "Taken": len(t),
            "Not Taken": max(len(s) - len(t), 0),
            "Wins": wins,
            "Losses": losses,
            "Win Rate": wins / (wins + losses) * 100 if wins + losses else None,
            "Net R": float(vals.sum()) if not vals.empty else None,
            "Net P&L": float(pd.to_numeric(t[pcol], errors="coerce").sum()) if pcol else None,
            "Max DD (R)": float((vals.cumsum() - vals.cumsum().cummax()).min()) if not vals.empty else None,
        })
    return pd.DataFrame(rows)


def render_strategy_lab():
    st.markdown("### ⚖️ S1–S5 strategy comparison")
    d = _stats()
    display = d.copy()
    display["Win Rate"] = display["Win Rate"].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
    for column in ["Net R", "Net P&L", "Max DD (R)"]:
        display[column] = display[column].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    st.dataframe(display, width="stretch", hide_index=True, height=300)

    if d["Signals"].sum() == 0:
        st.info("No verified signal/trade ledger yet; performance figures will populate from recorded results.")
    else:
        st.markdown("#### Comparison charts")
        st.bar_chart(d.set_index("Strategy")["Win Rate"].fillna(0), height=170)
        st.bar_chart(d.set_index("Strategy")["Net R"].fillna(0), height=170)
        st.bar_chart(d.set_index("Strategy")[["Signals", "Taken", "Not Taken"]], height=180)

    st.markdown("#### 🎯 Signal-picking rule")
    st.caption(
        "The dashboard is explanatory only. The production engine evaluates S1–S5 after the master market gate, then prioritizes sector-aligned stocks by news ranking."
    )
    priority = pd.DataFrame([
        {"Priority": "1", "Check": "Master market gate", "Rule": "NIFTY 500 sign + A/D + sector majority agree; ≥98% fresh coverage"},
        {"Priority": "2", "Check": "Sector eligibility", "Rule": "Stock belongs to a sector moving in the same direction as the master side"},
        {"Priority": "3", "Check": "News priority", "Rule": "Positive news ranks BUY candidates; negative news ranks SELL candidates"},
        {"Priority": "4", "Check": "Strategy validity", "Rule": "S1–S5 executable setup and risk/sizing checks must pass"},
        {"Priority": "5", "Check": "Decision deadline", "Rule": "Cycle must finish within the configured decision window"},
    ])
    with st.expander("View production signal-picking rules", expanded=False):
        st.dataframe(priority, width="stretch", hide_index=True)

    st.markdown("#### ⏱️ Signal → Entry → Exit")
    s = _read("signals.csv")
    if not s.empty:
        cols = [
            c for c in s.columns
            if str(c).lower() in {
                "timestamp", "time", "signal_time", "entry_time", "exit_time", "strategy",
                "strategy_id", "signal", "side", "entry", "sl", "stop_loss", "target", "exit", "status",
                "news_sentiment", "news_strength_score", "news_priority_rank", "news_headline",
            }
        ]
        st.dataframe(s[cols].tail(100) if cols else s.tail(100), width="stretch", hide_index=True, height=260)
    else:
        st.info("No signal timing records yet.")

    st.markdown("#### 📖 Executable S1–S5 contract")
    theory = {
        "S1": "Open beyond PDH/PDL → level is touched/swept → live LTP reclaims the open.",
        "S2": "PDH/PDL breakout → completed intraday retest → live reclaim/failure.",
        "S3": "Open inside PDH/PDL → opposite-side sweep → live reversal through the open.",
        "S4": "Break the previously completed intraday high/low; completed previous candle is required.",
        "S5": "Direct live LTP breakout of PDH/PDL.",
    }
    rows = []
    for sid, name in STRATEGIES.items():
        rows.append({
            "Strategy": sid,
            "Name": name,
            "Executable setup": theory[sid],
            "Target": "1.25R",
            "Risk": "₹1,400–₹1,500 actual risk; ₹2.5L max capital/trade",
            "Session": "09:45–14:00 entries; force square-off 15:00 IST",
            "Paper mode": "YES",
        })
    with st.expander("View complete S1–S5 contract", expanded=False):
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=280)
