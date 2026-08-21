"""Primary NSE Catalyst Streamlit entrypoint.

The dashboard is intentionally presentation-only.  One live engine cycle owns
Dhan collection; the dashboard reads the shared 15-second snapshot through the
canonical breadth layer.  Diagnostic/testing UI is kept out of production UI.
"""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

# Production dashboard only.  The separate TESTING panel is intentionally not
# rendered here; its files remain in the repository for CI/regression coverage.
from dashboard.single_master import render_dashboard

render_dashboard()
