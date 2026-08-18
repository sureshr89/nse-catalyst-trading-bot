from pathlib import Path
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from dashboard.strategy2_data import S2_TRADES, S2_SIGNALS, S2_DIAGNOSTICS, S2_STATE, GAPS, BOT_STATUS

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Downloads", page_icon="⬇️", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
ensure_bot_running()
render_nav()

st.title("⬇️ Strategy 2 — Downloads")
st.caption("All files below belong only to the separate ₹2,50,000 Strategy 2 paper account. Live state is owned by the main paper-bot worker.")

files = [
    (S2_TRADES, "Strategy 2 Trades", "strategy2_trades.csv", "text/csv"),
    (S2_SIGNALS, "Strategy 2 Signals", "strategy2_signals.csv", "text/csv"),
    (S2_DIAGNOSTICS, "Strategy 2 Diagnostics", "strategy2_diagnostics.json", "application/json"),
    (S2_STATE, "Strategy 2 Paper State", "strategy2_paper_engine_state.json", "application/json"),
    (GAPS, "Opening Gap Board", "strategy2_gap_analysis.csv", "text/csv"),
    (BOT_STATUS, "Main Paper-Bot Status", "nifty500_bot_status.json", "application/json"),
]
for path, label, filename, mime in files:
    if path.exists():
        st.download_button(f"Download {label}", path.read_bytes(), file_name=filename, mime=mime, use_container_width=True)
    else:
        st.info(f"{label}: not created yet.")

st.info("The legacy strategy2_status.json worker file is intentionally not exposed here because it is no longer the live Strategy 2 source of truth.")
render_daily_footer()
