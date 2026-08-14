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

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
render_nav(24)

st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;width:100%!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]{width:auto!important;max-width:none!important;min-width:0!important;flex:none!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:10px!important;padding:8px!important;min-height:52px!important;box-sizing:border-box!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricLabel"]{font-size:.58rem!important;color:#9fb0c7!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricValue"]{font-size:.84rem!important;color:#f4f7fb!important;font-weight:750!important;line-height:1.2!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricDelta"]{font-size:.62rem!important}
[data-testid="stAppViewContainer"] h1{font-size:1.18rem!important;line-height:1.2!important;font-weight:700!important;margin:.1rem 0 .12rem!important}
[data-testid="stAppViewContainer"] h2,[data-testid="stAppViewContainer"] h3{font-size:.86rem!important;line-height:1.25!important;font-weight:650!important;margin:.6rem 0 .28rem!important}
[data-testid="stAppViewContainer"] p,[data-testid="stAppViewContainer"] .stMarkdown{font-size:.82rem!important;line-height:1.35!important}
[data-testid="stPlotlyChart"],.js-plotly-plot,.plot-container,.svg-container,[data-testid="stPlotlyChart"] canvas,[data-testid="stPlotlyChart"] svg{pointer-events:none!important;touch-action:none!important;user-select:none!important;-webkit-user-select:none!important}
</style>
""", unsafe_allow_html=True)

# Execute the complete analysis renderer once. This avoids the old import/reload
# path that rendered duplicate Plotly elements and caused StreamlitDuplicateElementKey.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(str(DASHBOARD_DIR / "analysis.py"), run_name="__analysis_page__")
finally:
    st.set_page_config = _original_set_page_config
