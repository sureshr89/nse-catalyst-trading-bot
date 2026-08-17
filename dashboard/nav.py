import streamlit as st


def _button(label, page, key):
    if st.button(label, key=key, width="stretch"):
        st.switch_page(page)


def render_nav(top_offset=0):
    """Shared 2x2 navigation for desktop and mobile. News is intentionally absent."""
    offset = max(0, int(top_offset or 0))
    st.markdown(
        f"""
<style>
/* Navigation visual system */
.dashboard-nav {{
    margin:{offset}px 0 18px;
    width:100%;
}}
.dashboard-nav-title {{
    font-size:.70rem;
    font-weight:800;
    letter-spacing:.06em;
    margin:10px 0 7px;
    text-transform:uppercase;
    color:#A9B7CA;
}}
.dashboard-nav-title.s1 {{ color:#79B4FF; }}
.dashboard-nav-title.s2 {{ color:#FF9292; }}

/* Streamlit normally stacks columns on narrow screens.  Force every
   two-column navigation row to remain a true 2-column grid. */
@media(max-width:900px) {{
    [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) {{
        flex-direction:row !important;
        flex-wrap:nowrap !important;
        align-items:stretch !important;
        gap:0.65rem !important;
    }}
    [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) > [data-testid="column"] {{
        width:calc(50% - .325rem) !important;
        min-width:calc(50% - .325rem) !important;
        flex:1 1 0 !important;
    }}
}}

.dashboard-nav .stButton {{ width:100%; }}
.dashboard-nav .stButton > button {{
    width:100% !important;
    min-height:58px !important;
    padding:9px 8px !important;
    border:1px solid #303A4B !important;
    border-radius:14px !important;
    background:linear-gradient(145deg,#151B26,#11161F) !important;
    color:#F1F5FA !important;
    font-size:.82rem !important;
    font-weight:700 !important;
    line-height:1.15 !important;
    white-space:nowrap !important;
    box-shadow:0 3px 10px rgba(0,0,0,.16) !important;
    transition:all .15s ease !important;
}}
.dashboard-nav .stButton > button:hover {{
    border-color:#59769F !important;
    background:#192233 !important;
    transform:translateY(-1px);
}}
.dashboard-nav-title.s1 ~ [data-testid="stHorizontalBlock"] .stButton > button {{
    border-color:#294A73 !important;
}}
.dashboard-nav-title.s2 ~ [data-testid="stHorizontalBlock"] .stButton > button {{
    border-color:#63383D !important;
}}

@media(max-width:600px) {{
    .dashboard-nav {{ margin:{offset}px 0 13px; }}
    .dashboard-nav-title {{
        font-size:.64rem;
        margin:8px 0 6px;
        letter-spacing:.055em;
    }}
    .dashboard-nav .stButton > button {{
        min-height:62px !important;
        font-size:.75rem !important;
        padding:8px 5px !important;
        border-radius:13px !important;
    }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="dashboard-nav">', unsafe_allow_html=True)

        st.markdown('<div class="dashboard-nav-title">🏠 MAIN</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="small")
        with a:
            _button("🔵  STRATEGY 1", "pages/current_trading.py", "nav_home_s1")
        with b:
            _button("🔴  STRATEGY 2", "pages/strategy2.py", "nav_home_s2")

        st.markdown('<div class="dashboard-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="small")
        with a:
            _button("📌  CURRENT", "pages/current_trading.py", "nav_s1_current")
        with b:
            _button("📊  ANALYSIS", "pages/analysis.py", "nav_s1_analysis")
        a, b = st.columns(2, gap="small")
        with a:
            _button("🔎  SCANNER", "pages/stock_scanner.py", "nav_s1_scanner")
        with b:
            _button("⬇️  DOWNLOADS", "pages/downloads.py", "nav_s1_downloads")

        st.markdown('<div class="dashboard-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="small")
        with a:
            _button("📌  CURRENT", "pages/strategy2_current.py", "nav_s2_current")
        with b:
            _button("📊  ANALYSIS", "pages/strategy2_analysis.py", "nav_s2_analysis")
        a, b = st.columns(2, gap="small")
        with a:
            _button("🔎  SCANNER", "pages/strategy2_scanner.py", "nav_s2_scanner")
        with b:
            _button("⬇️  DOWNLOADS", "pages/strategy2_downloads.py", "nav_s2_downloads")

        st.markdown('</div>', unsafe_allow_html=True)
