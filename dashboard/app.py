"""NSE Catalyst Streamlit entry point.

The page does NOT auto-refresh. The user explicitly refreshes Dhan data with
one button, so the screen stays stable while reviewing closed-session values.
"""
from pathlib import Path
import runpy
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

_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(
        str(ROOT / "dashboard" / "single_master.py"),
        run_name="__nse_catalyst_dashboard__",
    )
    from dashboard.enhancements import render_enhancements
    render_enhancements()
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
