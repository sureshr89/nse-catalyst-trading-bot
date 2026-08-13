"""Analysis page wrapper with common 4-button navigation."""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1500px!important;padding:.45rem .55rem 1.5rem!important}
.nav-grid [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.55rem!important}
.nav-grid [data-testid="stColumn"]{width:calc(50% - .28rem)!important;flex:0 0 calc(50% - .28rem)!important;min-width:0!important}
.nav-grid [data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.4rem .2rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.66rem!important;font-weight:700!important;text-decoration:none!important;width:100%!important;box-sizing:border-box!important}
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
@media(max-width:768px){.block-container{padding:.35rem .35rem 1rem!important}.nav-grid [data-testid="stHorizontalBlock"]{gap:.35rem!important}.nav-grid [data-testid="stPageLink"] a{min-height:40px!important;font-size:.60rem!important}}
</style>
""",unsafe_allow_html=True)

with st.container(key="nav_grid"):
    n1,n2=st.columns(2,gap="small")
    n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢",width="stretch")
    n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌",width="stretch")
    n3,n4=st.columns(2,gap="small")
    n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊",width="stretch")
    n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️",width="stretch")

# Load the original full research dashboard. Its own set_page_config is
# temporarily suppressed because this wrapper already configured the page.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    from dashboard import analysis as _full_analysis
finally:
    st.set_page_config = _original_set_page_config
