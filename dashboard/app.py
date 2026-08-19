"""Reliable Streamlit entry point for NSE Catalyst."""
import streamlit as st

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
    from dashboard.single_master import *  # noqa: F401,F403
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
