import streamlit as st


def _link(label, page):
    """Use Streamlit's native page navigation without unsupported key arguments."""
    st.page_link(page, label=label)


def _row(left, right):
    """Stable two-column navigation that remains usable on mobile."""
    cols = st.columns(2, gap="small")
    with cols[0]:
        _link(left[0], left[1])
    with cols[1]:
        _link(right[0], right[1])


def render_nav(top_offset=0):
    """Mobile-friendly 2x2 navigation. News is intentionally absent."""
    if top_offset:
        st.write("")
        st.write("")

    st.markdown("""
    <style>
    .nse-nav-title{font-size:.72rem;font-weight:800;letter-spacing:.05em;margin:8px 0 6px;text-transform:uppercase}
    .nse-nav-title.main{color:#A9B7CA}.nse-nav-title.s1{color:#79B4FF}.nse-nav-title.s2{color:#FF9292}
    [data-testid="stPageLink"]{width:100%!important}
    [data-testid="stPageLink"] a{width:100%!important;min-height:50px!important;border:1px solid #303A4B!important;border-radius:12px!important;background:#151B26!important;padding:7px 5px!important;box-sizing:border-box!important;justify-content:center!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
    [data-testid="stPageLink"] a:hover{border-color:#59769F!important;background:#192233!important}
    [data-testid="stPageLink"] a p{overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;margin:0!important}
    @media(max-width:600px){[data-testid="stPageLink"] a{min-height:48px!important;padding:6px 3px!important;font-size:.76rem!important}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="nse-nav-title main">🏠 MAIN</div>', unsafe_allow_html=True)
    _row(("🔵 STRATEGY 1", "pages/current_trading.py"), ("🔴 STRATEGY 2", "pages/strategy2.py"))

    st.markdown('<div class="nse-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT", "pages/current_trading.py"), ("📊 ANALYSIS", "pages/analysis.py"))
    _row(("🔎 SCANNER", "pages/stock_scanner.py"), ("⬇️ DOWNLOADS", "pages/downloads.py"))

    st.markdown('<div class="nse-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT", "pages/strategy2_current.py"), ("📊 ANALYSIS", "pages/strategy2_analysis.py"))
    _row(("🔎 SCANNER", "pages/strategy2_scanner.py"), ("⬇️ DOWNLOADS", "pages/strategy2_downloads.py"))
