"""Downloads for the NIFTY 500 paper-trading strategy."""
from pathlib import Path
import json
import sys
import pandas as pd
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from master_data import build_master_data

st.set_page_config(page_title="NSE Catalyst | Downloads", page_icon="⬇️", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)
try:
    ensure_bot_running()
except Exception:
    pass


def read_csv(name):
    try:
        path = ROOT / "outputs" / name
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def clean(frame):
    if frame.empty:
        return frame
    blocked = [c for c in frame.columns if "atr" in str(c).lower() or "average_true_range" in str(c).lower()]
    return frame.drop(columns=blocked, errors="ignore")


def json_bytes(name, fallback):
    path = ROOT / "outputs" / name
    try:
        return path.read_bytes() if path.exists() else json.dumps(fallback, indent=2).encode("utf-8")
    except Exception:
        return json.dumps(fallback, indent=2).encode("utf-8")

try:
    build_master_data()
except Exception:
    pass

trades = clean(read_csv("trades.csv"))
signals = clean(read_csv("signals.csv"))
gaps = read_csv("gap_analysis.csv")
master = clean(read_csv("MASTER_TRADES.csv"))
daily = clean(read_csv("MASTER_DAILY_STOCK_DATA.csv"))

st.title("⬇️ Downloads")
st.caption("Paper-trading records, NIFTY 500 GAP board, scanner state and bot status. No news data is collected or exported.")

st.subheader("📁 Trading Data")
st.download_button("⬇️ TRADES CSV", data=trades.to_csv(index=False).encode("utf-8"), file_name="nifty500_trades.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ SIGNALS CSV", data=signals.to_csv(index=False).encode("utf-8"), file_name="nifty500_signals.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ PREMARKET GAP BOARD CSV", data=gaps.to_csv(index=False).encode("utf-8"), file_name="nifty500_premarket_gap_board.csv", mime="text/csv", width="stretch")

st.subheader("⭐ Master Trading Data")
st.download_button("⬇️ MASTER TRADES CSV", data=master.to_csv(index=False).encode("utf-8"), file_name="NSE_CATALYST_MASTER_TRADES.csv", mime="text/csv", width="stretch")
st.download_button("⬇️ MASTER DAILY STOCK DATA CSV", data=daily.to_csv(index=False).encode("utf-8"), file_name="NSE_CATALYST_MASTER_DAILY_STOCK_DATA.csv", mime="text/csv", width="stretch")

st.subheader("⏳ Scanner State")
st.download_button("⬇️ WAITING / QUALIFIED JSON", data=json_bytes("waiting_candidates.json", {"waiting": {"BUY": {}, "SELL": {}}, "qualified": {"BUY": {}, "SELL": {}}}), file_name="nifty500_waiting_candidates.json", mime="application/json", width="stretch")
st.download_button("⬇️ SCANNER DIAGNOSTICS JSON", data=json_bytes("scanner_diagnostics.json", {"nifty500_change_pct": 0, "buy_waiting": 0, "sell_waiting": 0, "buy_qualified": 0, "sell_qualified": 0, "ranking": []}), file_name="nifty500_scanner_diagnostics.json", mime="application/json", width="stretch")

st.subheader("⚙️ Bot Records")
st.download_button("⬇️ BOT STATUS JSON", data=json_bytes("bot_status.json", {"status": "WAITING", "worker_alive": False}), file_name="nifty500_bot_status.json", mime="application/json", width="stretch")
st.download_button("⬇️ PAPER STATE JSON", data=json_bytes("paper_engine_state.json", {"strategy": "NIFTY_500_PDH_PDL_OPEN_RETURN", "open_positions": {}, "available_capital": 250000}), file_name="nifty500_paper_state.json", mime="application/json", width="stretch")

st.subheader("📌 Premarket GAP Board")
if not gaps.empty and "GapType" in gaps.columns:
    gap_frame = gaps.copy()
    gap_frame["GapPercent"] = pd.to_numeric(gap_frame.get("GapPercent"), errors="coerce")
    left, right = st.columns(2)
    with left:
        st.markdown("**🟢 Gap Up — Open > PDH**")
        st.dataframe(gap_frame[gap_frame["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False).head(30), width="stretch", hide_index=True, height=350)
    with right:
        st.markdown("**🔴 Gap Down — Open < PDL**")
        st.dataframe(gap_frame[gap_frame["GapType"].eq("GAP_DOWN")].sort_values("GapPercent").head(30), width="stretch", hide_index=True, height=350)
else:
    st.info("GAP board will appear after current market data is available.")

st.info("Strategy decisions use price, GAP, PDH/PDL, NIFTY 500 alignment, risk and completed 1-minute candles. News is not used.")
render_daily_footer()
