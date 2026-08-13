"""Analysis page wrapper."""
import importlib
import streamlit as st
from dashboard.nav import render_nav

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
render_nav(16)
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from dashboard import analysis as _full_analysis
    importlib.reload(_full_analysis)
finally:
    st.set_page_config = _original_set_page_config
