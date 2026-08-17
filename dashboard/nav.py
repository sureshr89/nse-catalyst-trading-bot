import streamlit as st


def _button(label, page, key):
    if st.button(label, key=key, width="stretch"):
        st.switch_page(page)


def render_nav(top_offset=0):
    """Compact 2x2 navigation that remains usable on phone screens. News is absent."""
    offset = max(0, int(top_offset or 0))
    st.markdown(
        f"""
<style>
/* The columns themselves own the width. Do NOT make the Streamlit button
   wrapper wider than its column: that was causing the second column to
   render off-screen on mobile. */
.dashboard-nav {{ margin:{offset}px 0 14px; width:100%; overflow:visible; }}
.dashboard-nav-title {{ font-size:.70rem; font-weight:800; letter-spacing:.055em; margin:9px 0 6px; text-transform:uppercase; color:#A9B7CA; }}
.dashboard-nav-title.s1 {{ color:#79B4FF; }}
.dashboard-nav-title.s2 {{ color:#FF9292; }}

/* Keep navigation rows as two equal columns on phones. */
@media(max-width:900px) {{
    [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) {{
        flex-direction:row !important;
        flex-wrap:nowrap !important;
        width:100% !important;
        max-width:100% !important;
        box-sizing:border-box !important;
        gap:.55rem !important;
    }}
    [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) > [data-testid="column"] {{
        width:calc(50% - .275rem) !important;
        min-width:0 !important;
        max-width:calc(50% - .275rem) !important;
        flex:0 0 calc(50% - .275rem) !important;
        box-sizing:border-box !important;
    }}
}}

.dashboard-nav .stButton {{ width:auto !important; max-width:100% !important; }}
.dashboard-nav .stButton > button {{
    width:100% !important;
    max-width:100% !important;
    min-height:56px !important;
    padding:8px 6px !important;
    border:1px solid #303A4B !important;
    border-radius:13px !important;
    background:#151B26 !important;
    color:#F1F5FA !important;
    font-size:.80rem !important;
    font-weight:700 !important;
    line-height:1.1 !important;
    white-space:nowrap !important;
    box-sizing:border-box !important;
    box-shadow:0 2px 8px rgba(0,0,0,.14) !important;
}}
.dashboard-nav .stButton > button:hover {{ border-color:#59769F !important; background:#192233 !important; }}

@media(max-width:600px) {{
    .dashboard-nav {{ margin:{offset}px 0 12px; }}
    .dashboard-nav-title {{ font-size:.62rem; margin:7px 0 5px; }}
    .dashboard-nav .stButton > button {{
        min-height:58px !important;
        font-size:.73rem !important;
        padding:7px 3px !important;
        border-radius:12px !important;
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
            _button("🔵 STRATEGY 1", "pages/current_trading.py", "nav_home_s1")
        with b:
            _button("🔴 STRATEGY 2", "pages/strategy2.py", "nav_home_s2")

        st.markdown('<div class="dashboard-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="small")
        with a:
            _button("📌 CURRENT", "pages/current_trading.py", "nav_s1_current")
        with b:
            _button("📊 ANALYSIS", "pages/analysis.py", "nav_s1_analysis")
        a, b = st.columns(2, gap="small")
        with a:
            _button("🔎 SCANNER", "pages/stock_scanner.py", "nav_s1_scanner")
        with b:
            _button("⬇️ DOWNLOADS", "pages/downloads.py", "nav_s1_downloads")

        st.markdown('<div class="dashboard-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="small")
        with a:
            _button("📌 CURRENT", "pages/strategy2_current.py", "nav_s2_current")
        with b:
            _button("📊 ANALYSIS", "pages/strategy2_analysis.py", "nav_s2_analysis")
        a, b = st.columns(2, gap="small")
        with a:
            _button("🔎 SCANNER", "pages/strategy2_scanner.py", "nav_s2_scanner")
        with b:
            _button("⬇️ DOWNLOADS", "pages/strategy2_downloads.py", "nav_s2_downloads")

        st.markdown('</div>', unsafe_allow_html=True)
