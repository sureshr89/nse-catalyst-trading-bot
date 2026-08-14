"""Analysis page wrapper."""
import runpy
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
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from worker_service import ensure_worker_process

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)
try:
    ensure_worker_process()
except Exception as error:
    st.warning(f"Worker launcher: {type(error).__name__}: {error}")

st.markdown('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}</style>', unsafe_allow_html=True)
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(str(DASHBOARD_DIR / "analysis.py"), run_name="__analysis_page__")
finally:
    st.set_page_config = _original_set_page_config
render_daily_footer()
