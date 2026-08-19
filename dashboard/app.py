"""NSE Catalyst mobile-first dashboard."""
from pathlib import Path
import sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
try:
    from dashboard.enhancements import render_enhancements
    render_enhancements()
    st.markdown("""
    <style>
    .stApp{background:#000000!important;color:#F5F7FB!important}
    .main,.block-container{background:#000000!important}
    [data-testid="stHeader"]{background:#000000!important}
    h1,h2,h3,h4,h5,h6,p,span,div{color:inherit}
    .box{background:#0B0F14!important;border:1px solid #26313D!important;box-shadow:none!important;color:#F5F7FB!important}
    .cell{background:#111820!important;border:1px solid #202A34!important}
    .title,.lab{color:#AAB6C3!important}.val,.big,.shead{color:#F5F7FB!important}
    .pill{background:#092C32!important;color:#5DE7F5!important}.strat{border-left-color:#00D9FF!important}
    .tip{background:#0B2023!important;border:1px solid #164B50!important;color:#D8F7FA!important}
    .hero{background:linear-gradient(135deg,#020406,#07151F,#062B32)!important;border:1px solid #17313A!important;box-shadow:none!important}
    .hero h1,.hero small,.hero .time{color:#F5F7FB!important}.stMarkdown h3{color:#F5F7FB!important}
    </style>
    """,unsafe_allow_html=True)
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
