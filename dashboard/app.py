"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="NSE Catalyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import main as _engine_main


@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()


@st.fragment(run_every="15s")
def _live_trade_worker():
    """Run the single production cycle; all consumers share its snapshot."""
    try:
        engine = _get_trading_engine()
        engine.run_cycle()
        st.session_state["trade_worker_error"] = None
    except Exception as exc:
        st.session_state["trade_worker_error"] = f"{type(exc).__name__}: {exc}"


_live_trade_worker()

# Production UI only. Diagnostic/testing files remain available to CI but are
# intentionally not rendered in the live trading dashboard.
from dashboard.single_master import render_dashboard

render_dashboard()
