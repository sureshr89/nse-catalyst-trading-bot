"""NSE Catalyst minimal strategy selector landing page."""
import streamlit as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
st.set_page_config(
    page_title="NSE Catalyst",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .landing{max-width:900px;margin:18vh auto 0;padding:20px;text-align:center}
    .landing h1{font-size:clamp(2rem,5vw,3rem);margin-bottom:42px;font-weight:800}
    div.stButton>button{width:100%;min-height:72px;border-radius:16px;font-size:1.1rem;font-weight:800;background:#151B26;border:1px solid #344052}
    div.stButton>button:hover{background:#1C2636;border-color:#6A86AE}
    @media(max-width:700px){.landing{margin-top:12vh;padding:14px}div.stButton>button{min-height:64px;font-size:1rem}}
    </style>
    <div class="landing"><h1>NSE Catalyst</h1></div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns(2, gap="large")
with left:
    if st.button("🔵  STRATEGY 1", key="open_s1", use_container_width=True):
        st.switch_page("pages/current_trading.py")
with right:
    if st.button("🔴  STRATEGY 2", key="open_s2", use_container_width=True):
        st.switch_page("pages/strategy2_current.py")
