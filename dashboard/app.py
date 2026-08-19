"""NSE Catalyst strategy selector and explicit Streamlit page registry."""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
st.set_page_config(
    page_title="NSE Catalyst",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Explicitly register every page. This prevents StreamlitPageNotFoundError
# when custom navigation links are rendered from another page.
pages = [
    st.Page("pages/current_trading.py", title="Strategy 1", icon="🔵"),
    st.Page("pages/strategy2_current.py", title="Strategy 2", icon="🔴"),
    st.Page("pages/strategy3_current.py", title="Strategy 3", icon="🟢"),
    st.Page("pages/strategy4_current.py", title="Strategy 4", icon="🟣"),
    st.Page("pages/strategy5_current.py", title="Strategy 5", icon="🟠"),
    st.Page("pages/compare_strategies.py", title="Compare All", icon="📊"),
]

# Keep the built-in sidebar hidden; the app uses its own visual navigation.
pg = st.navigation(pages, position="hidden")

if pg.url_path:
    pg.run()
    st.stop()

st.markdown(
    """
    <style>
    .landing{max-width:1000px;margin:10vh auto 0;padding:20px;text-align:center}
    .landing h1{font-size:clamp(2rem,5vw,3.2rem);margin-bottom:12px;font-weight:850}
    .landing p{color:#9FB0C7;font-size:1rem;margin-bottom:38px}
    div.stButton>button{width:100%;min-height:72px;border-radius:16px;font-size:1.05rem;font-weight:800;background:#151B26;border:1px solid #344052}
    div.stButton>button:hover{background:#1C2636;border-color:#6A86AE}
    </style>
    <div class="landing">
      <h1>NSE Catalyst</h1>
      <p>🏠 STRATEGIES</p>
    </div>
    """,
    unsafe_allow_html=True,
)

buttons = [
    ("🔵 STRATEGY 1", "pages/current_trading.py", "open_s1"),
    ("🔴 STRATEGY 2", "pages/strategy2_current.py", "open_s2"),
    ("🟢 STRATEGY 3", "pages/strategy3_current.py", "open_s3"),
    ("🟣 STRATEGY 4", "pages/strategy4_current.py", "open_s4"),
    ("🟠 STRATEGY 5", "pages/strategy5_current.py", "open_s5"),
    ("📊 COMPARE ALL", "pages/compare_strategies.py", "open_compare"),
]

for start in range(0, len(buttons), 2):
    cols = st.columns(2, gap="large")
    for col, (label, page, key) in zip(cols, buttons[start:start+2]):
        with col:
            if st.button(label, key=key, use_container_width=True):
                st.switch_page(page)
