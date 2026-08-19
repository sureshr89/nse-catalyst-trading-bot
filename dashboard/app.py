"""Reliable Streamlit entry point for NSE Catalyst."""
from pathlib import Path
import sys
import streamlit as st

# Streamlit executes this file as dashboard/app.py. Add the repository root to
# Python's import path so both dashboard/single_master.py and top-level packages
# such as data/ and market/ can be imported reliably on Streamlit Cloud.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="NSE Catalyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("# 📊 NSE Catalyst")
st.caption("Starting dashboard…")

# single_master.py also configures the page. Disable its second page-config
# call when it is imported through this entry point.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None

try:
    # Import the sibling module directly. Using `dashboard.single_master`
    # fails on Streamlit Cloud because dashboard is not a Python package.
    from single_master import *  # noqa: F401,F403
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
