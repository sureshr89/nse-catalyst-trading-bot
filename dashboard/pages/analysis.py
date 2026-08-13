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

# Analysis metric rows are deliberately 2x2 so all four account/strategy values
# remain visible on mobile and desktop. Chart rows already use two columns and
# therefore keep the same clean layout.
st.markdown("""
<style>
/* Keep every analysis metric row at exactly two columns. */
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){
    display:flex!important;
    flex-wrap:wrap!important;
    gap:.65rem!important;
    width:100%!important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]{
    width:calc(50% - .325rem)!important;
    max-width:calc(50% - .325rem)!important;
    min-width:0!important;
    flex:0 0 calc(50% - .325rem)!important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetric"]{
    width:100%!important;
    box-sizing:border-box!important;
}
</style>
""", unsafe_allow_html=True)

_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from dashboard import analysis as _full_analysis
    importlib.reload(_full_analysis)
finally:
    st.set_page_config = _original_set_page_config
