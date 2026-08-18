"""Strategy 2 downloads.

Layout intentionally mirrors the Strategy 1 Downloads page while exposing
only Strategy 2 data and state.
"""
from pathlib import Path
import sys
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from dashboard.strategy2_data import S2_TRADES, S2_SIGNALS, S2_DIAGNOSTICS, S2_STATE, GAPS, BOT_STATUS

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Downloads", page_icon="⬇️", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
try:
    ensure_bot_running()
except Exception:
    pass
render_nav()


def read_csv(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def read_bytes(path, fallback):
    try:
        return path.read_bytes() if path.exists() else json.dumps(fallback, indent=2).encode("utf-8")
    except Exception:
        return json.dumps(fallback, indent=2).encode("utf-8")


def clean(frame):
    if frame.empty:
        return frame
    blocked = [c for c in frame.columns if "atr" in str(c).lower() or "average_true_range" in str(c).lower()]
    return frame.drop(columns=blocked, errors="ignore")

trades = clean(read_csv(S2_TRADES))
signals = clean(read_csv(S2_SIGNALS))
gaps = read_csv(GAPS)

diagnostics_fallback = {"strategy_version": "STRATEGY_2", "candidates": 0, "buy_candidates": 0, "sell_candidates": 0, "signals": 0}
state_fallback = {"strategy": "STRATEGY_2", "open_positions": {}, "available_capital": 250000}
bot_fallback = {"status": "WAITING", "worker_alive": False}

st.title("⬇️ Strategy 2 — Downloads")
st.caption("Strategy 2 paper-trading records, opening GAP board, scanner state and bot status. Same organization as the Strategy 1 Downloads page.")

st.subheader("📁 Trading Data")
st.download_button("⬇️ STRATEGY 2 TRADES CSV", data=trades.to_csv(index=False).encode("utf-8"), file_name="strategy2_trades.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ STRATEGY 2 SIGNALS CSV", data=signals.to_csv(index=False).encode("utf-8"), file_name="strategy2_signals.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ PREMARKET GAP BOARD CSV", data=gaps.to_csv(index=False).encode("utf-8"), file_name="strategy2_premarket_gap_board.csv", mime="text/csv", width="stretch")

st.subheader("⭐ Strategy 2 Trading Data")
st.download_button("⬇️ STRATEGY 2 DIAGNOSTICS JSON", data=read_bytes(S2_DIAGNOSTICS, diagnostics_fallback), file_name="strategy2_diagnostics.json", mime="application/json", width="stretch")
st.download_button("⬇️ STRATEGY 2 PAPER STATE JSON", data=read_bytes(S2_STATE, state_fallback), file_name="strategy2_paper_engine_state.json", mime="application/json", width="stretch")

st.subheader("⏳ Scanner State")
st.download_button("⬇️ STRATEGY 2 GAP BOARD CSV", data=gaps.to_csv(index=False).encode("utf-8"), file_name="strategy2_gap_analysis.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ MAIN BOT STATUS JSON", data=read_bytes(BOT_STATUS, bot_fallback), file_name="nifty500_bot_status.json", mime="application/json", width="stretch")

st.subheader("📌 Premarket GAP Board")
if not gaps.empty:
    gap_frame = gaps.copy()
    gap_col = "GapPercentFromPreviousClose" if "GapPercentFromPreviousClose" in gap_frame.columns else "GapPercent" if "GapPercent" in gap_frame.columns else None
    if gap_col:
        gap_frame[gap_col] = pd.to_numeric(gap_frame[gap_col], errors="coerce")
        gap_frame["GapPriority"] = gap_frame[gap_col].abs()
        gap_frame = gap_frame.sort_values("GapPriority", ascending=False)
    left, right = st.columns(2)
    with left:
        st.markdown("**🟢 Gap Up — Open > PDH**")
        up = gap_frame[gap_frame.get("GapType", pd.Series(index=gap_frame.index)).astype(str).eq("GAP_UP")].head(30)
        st.dataframe(up, width="stretch", hide_index=True, height=350)
    with right:
        st.markdown("**🔴 Gap Down — Open < PDL**")
        down = gap_frame[gap_frame.get("GapType", pd.Series(index=gap_frame.index)).astype(str).eq("GAP_DOWN")].head(30)
        st.dataframe(down, width="stretch", hide_index=True, height=350)
else:
    st.info("GAP board will appear after current market data is available.")

st.info("Strategy 2 decisions use opening GAP, PDH/PDL, extension beyond Today's Open, first completed 1-minute reversal close and risk validation. Paper trading only.")
render_daily_footer()
