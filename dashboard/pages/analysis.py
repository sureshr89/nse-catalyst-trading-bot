"""Analysis page wrapper."""
import importlib
import sys
from pathlib import Path
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nav import render_nav

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
render_nav(24)
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from dashboard import analysis as _full_analysis
    importlib.reload(_full_analysis)
finally:
    st.set_page_config = _original_set_page_config
