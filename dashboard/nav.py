import streamlit as st


def _link(label, page, key):
    """Stable Streamlit button navigation."""
    if st.button(label, key=key, use_container_width=True):
        st.switch_page(page)


def _row(left, right):
    cols = st.columns(2, gap="small")
    with cols[0]:
        _link(left[0], left[1], left[2])
    with cols[1]:
        _link(right[0], right[1], right[2])


def render_nav(top_offset=0):
    """Mobile-friendly 2x2 navigation. News is intentionally absent."""
    if top_offset:
        st.write("")
        st.write("")
    st.markdown("""
    <style>
    .nse-nav-title{font-size:.72rem;font-weight:800;letter-spacing:.05em;margin:8px 0 6px;text-transform:uppercase}
    .nse-nav-title.main{color:#A9B7CA}.nse-nav-title.s1{color:#79B4FF}.nse-nav-title.s2{color:#FF9292}
    div[data-testid="stButton"]>button{width:100%!important;min-height:50px!important;border:1px solid #303A4B!important;border-radius:12px!important;background:#151B26!important;padding:7px 5px!important;box-sizing:border-box!important;white-space:nowrap!important;overflow:hidden!important}
    div[data-testid="stButton"]>button p{overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;margin:0!important}
    div[data-testid="stButton"]>button:hover{border-color:#59769F!important;background:#192233!important}
    @media(max-width:600px){div[data-testid="stButton"]>button{min-height:48px!important;padding:6px 3px!important;font-size:.76rem!important}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="nse-nav-title main">🏠 MAIN</div>', unsafe_allow_html=True)
    _row(("🔵 STRATEGY 1","pages/current_trading.py","nav_main_s1"),("🔴 STRATEGY 2","pages/strategy2.py","nav_main_s2"))
    st.markdown('<div class="nse-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT","pages/current_trading.py","nav_s1_current"),("📊 ANALYSIS","pages/analysis.py","nav_s1_analysis"))
    _row(("🔎 SCANNER","pages/stock_scanner.py","nav_s1_scanner"),("⬇️ DOWNLOADS","pages/downloads.py","nav_s1_downloads"))
    st.markdown('<div class="nse-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT","pages/strategy2_current.py","nav_s2_current"),("📊 ANALYSIS","pages/strategy2_analysis.py","nav_s2_analysis"))
    _row(("🔎 SCANNER","pages/strategy2_scanner.py","nav_s2_scanner"),("⬇️ DOWNLOADS","pages/strategy2_downloads.py","nav_s2_downloads"))
