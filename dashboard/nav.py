import streamlit as st


def _button(label, page, key):
    if st.button(label, key=key, width="stretch"):
        st.switch_page(page)


def render_nav(top_offset=0):
    """Shared, touch-friendly 2x2 navigation. News is intentionally absent."""
    offset = max(0, int(top_offset or 0))
    st.markdown(
        f"""
<style>
.dashboard-nav {{ margin:{offset}px 0 16px; width:100%; }}
.dashboard-nav-title {{ font-size:.68rem; font-weight:800; letter-spacing:.06em; margin:8px 0 6px; text-transform:uppercase; color:#9FB0C7; }}
.dashboard-nav-title.s1 {{ color:#7FB3FF; }}
.dashboard-nav-title.s2 {{ color:#FF8F8F; }}
.dashboard-nav .stButton {{ width:100%; }}
.dashboard-nav .stButton > button {{ width:100%!important; min-height:52px!important; padding:8px 7px!important; border:1px solid #2b3b57!important; border-radius:11px!important; background:#142036!important; color:#E9F0F8!important; font-size:.78rem!important; font-weight:650!important; line-height:1.1!important; white-space:nowrap!important; }}
.dashboard-nav .s1-row .stButton > button {{ border-color:#2C4E79!important; }}
.dashboard-nav .s2-row .stButton > button {{ border-color:#704044!important; }}
.dashboard-nav .main-row .stButton > button {{ min-height:46px!important; }}
@media(max-width:600px) {{
  .dashboard-nav {{ margin:{offset}px 0 12px; }}
  .dashboard-nav .stButton > button {{ min-height:54px!important; font-size:.72rem!important; padding:8px 5px!important; }}
  .dashboard-nav-title {{ font-size:.62rem; margin:6px 0 5px; }}
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
