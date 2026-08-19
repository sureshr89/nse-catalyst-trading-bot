"""Reliable Streamlit entry point for NSE Catalyst."""
from pathlib import Path
import runpy
import sys
import threading
import time
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

try:
    from market.nifty500_breadth import BREADTH

    if not hasattr(BREADTH, "_async_dashboard_state"):
        BREADTH._async_dashboard_state = {
            "market": {
                "complete": False,
                "sector_complete": False,
                "reason": "DATA_LOADING",
                "evaluated": 0,
                "total": 500,
            },
            "running": False,
            "error": None,
            "started_at": 0.0,
        }
        BREADTH._sync_dashboard_snapshot = BREADTH.snapshot

    def _background_dhan_scan():
        state = BREADTH._async_dashboard_state
        try:
            result = BREADTH._sync_dashboard_snapshot(force=True)
            state["market"] = result
            state["error"] = None
        except Exception as exc:
            state["error"] = f"{type(exc).__name__}: {exc}"
            state["market"] = {
                "complete": False,
                "sector_complete": False,
                "reason": state["error"],
                "evaluated": 0,
                "total": 500,
            }
        finally:
            state["running"] = False

    def _non_blocking_snapshot(force=False):
        state = BREADTH._async_dashboard_state
        if not state["running"]:
            state["running"] = True
            state["started_at"] = time.monotonic()
            threading.Thread(target=_background_dhan_scan, name="dhan-nifty500-scan", daemon=True).start()
        return dict(state["market"])

    BREADTH.snapshot = _non_blocking_snapshot
except Exception:
    pass

_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__nse_catalyst_dashboard__")
    from dashboard.enhancements import render_enhancements
    render_enhancements()
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
