"""NSE Catalyst strategy selector landing page.

The landing page is intentionally minimal: strategy selection only.  All live
trading data, positions, charts, analysis and downloads stay inside the
selected strategy's dedicated pages.
"""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="NSE Catalyst | Select Strategy",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .landing-wrap{max-width:900px;margin:10vh auto 0;padding:24px;text-align:center}
    .landing-title{font-size:clamp(2rem,5vw,3.4rem);font-weight:800;letter-spacing:-.03em;margin-bottom:8px}
    .landing-subtitle{font-size:1rem;color:#9AA8BA;margin-bottom:42px}
    .strategy-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
    .strategy-card{border:1px solid #303A4B;border-radius:18px;background:#151B26;padding:28px 20px;min-height:150px;display:flex;flex-direction:column;justify-content:center}
    .strategy-card h2{margin:0 0 8px;font-size:1.45rem}
    .strategy-card p{margin:0;color:#9AA8BA;font-size:.9rem}
    @media(max-width:700px){
      .landing-wrap{margin:7vh auto 0;padding:16px}
      .strategy-grid{grid-template-columns:1fr;gap:16px}
      .strategy-card{min-height:125px}
    }
    div.stButton > button{width:100%;min-height:62px;border-radius:14px;font-size:1.05rem;font-weight:800;border:1px solid #3A4658;background:#182131}
    div.stButton > button:hover{border-color:#6A86AE;background:#1D293B}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="landing-wrap">', unsafe_allow_html=True)
st.markdown('<div class="landing-title">NSE Catalyst</div>', unsafe_allow_html=True)
st.markdown('<div class="landing-subtitle">Select a strategy</div>', unsafe_allow_html=True)

left, right = st.columns(2, gap="large")
with left:
    st.markdown('<div class="strategy-card"><h2>🔵 Strategy 1</h2><p>PDH / PDL Return</p></div>', unsafe_allow_html=True)
    if st.button("Open Strategy 1", key="open_s1", use_container_width=True):
        st.switch_page("pages/current_trading.py")
with right:
    st.markdown('<div class="strategy-card"><h2>🔴 Strategy 2</h2><p>Gap Extension Reversal</p></div>', unsafe_allow_html=True)
    if st.button("Open Strategy 2", key="open_s2", use_container_width=True):
        st.switch_page("pages/strategy2_current.py")

st.markdown('</div>', unsafe_allow_html=True)
