import streamlit as st


def _button(label, page, key):
    if st.button(label, key=key, width="stretch"):
        st.switch_page(page)


def _row(key, left, right):
    """Render exactly two equal-width navigation buttons without st.columns."""
    with st.container(
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
        gap="small",
        width="stretch",
        key=key,
    ):
        _button(left[0], left[1], left[2])
        _button(right[0], right[1], right[2])


def render_nav(top_offset=0):
    """Compact 2x2 navigation that stays fully visible on phones. News is absent."""
    offset = max(0, int(top_offset or 0))
    st.markdown(
        f"""
<style>
/* Responsive navigation: horizontal containers are used instead of
   st.columns because Streamlit columns can overflow/stack on narrow phones. */
.dashboard-nav {{
    margin:{offset}px 0 14px;
    width:100%;
    max-width:100%;
    overflow:visible;
    box-sizing:border-box;
}}
.dashboard-nav-title {{
    font-size:.70rem;
    font-weight:800;
    letter-spacing:.055em;
    margin:9px 0 6px;
    text-transform:uppercase;
    color:#A9B7CA;
}}
.dashboard-nav-title.s1 {{ color:#79B4FF; }}
.dashboard-nav-title.s2 {{ color:#FF9292; }}

/* Each keyed horizontal row contains exactly two buttons. */
.dashboard-nav [class*="st-key-nav-row-"] {{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    box-sizing:border-box !important;
    overflow:visible !important;
}}
.dashboard-nav [class*="st-key-nav-row-"] > [data-testid="stButton"] {{
    flex:1 1 0 !important;
    width:0 !important;
    min-width:0 !important;
    max-width:100% !important;
    box-sizing:border-box !important;
}}
.dashboard-nav [class*="st-key-nav-row-"] [data-testid="stButton"] > button {{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    box-sizing:border-box !important;
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
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    box-shadow:0 2px 8px rgba(0,0,0,.14) !important;
}}
.dashboard-nav [class*="st-key-nav-row-"] [data-testid="stButton"] > button:hover {{
    border-color:#59769F !important;
    background:#192233 !important;
}}

@media(max-width:600px) {{
    .dashboard-nav {{ margin:{offset}px 0 12px; }}
    .dashboard-nav-title {{
        font-size:.62rem;
        margin:7px 0 5px;
    }}
    .dashboard-nav [class*="st-key-nav-row-"] {{
        gap:.45rem !important;
    }}
    .dashboard-nav [class*="st-key-nav-row-"] [data-testid="stButton"] > button {{
        min-height:54px !important;
        font-size:.70rem !important;
        padding:7px 3px !important;
        border-radius:11px !important;
    }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="dashboard-nav">', unsafe_allow_html=True)

        st.markdown('<div class="dashboard-nav-title">🏠 MAIN</div>', unsafe_allow_html=True)
        _row(
            "nav-row-main",
            ("🔵 STRATEGY 1", "pages/current_trading.py", "nav_home_s1"),
            ("🔴 STRATEGY 2", "pages/strategy2.py", "nav_home_s2"),
        )

        st.markdown('<div class="dashboard-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
        _row(
            "nav-row-s1-top",
            ("📌 CURRENT", "pages/current_trading.py", "nav_s1_current"),
            ("📊 ANALYSIS", "pages/analysis.py", "nav_s1_analysis"),
        )
        _row(
            "nav-row-s1-bottom",
            ("🔎 SCANNER", "pages/stock_scanner.py", "nav_s1_scanner"),
            ("⬇️ DOWNLOADS", "pages/downloads.py", "nav_s1_downloads"),
        )

        st.markdown('<div class="dashboard-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
        _row(
            "nav-row-s2-top",
            ("📌 CURRENT", "pages/strategy2_current.py", "nav_s2_current"),
            ("📊 ANALYSIS", "pages/strategy2_analysis.py", "nav_s2_analysis"),
        )
        _row(
            "nav-row-s2-bottom",
            ("🔎 SCANNER", "pages/strategy2_scanner.py", "nav_s2_scanner"),
            ("⬇️ DOWNLOADS", "pages/strategy2_downloads.py", "nav_s2_downloads"),
        )

        st.markdown('</div>', unsafe_allow_html=True)
