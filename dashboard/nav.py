import streamlit as st


def _button(label, page, key):
    if st.button(label, key=key, width="stretch"):
        st.switch_page(page)


def render_nav(top_offset=0):
    """Stable, aligned navigation shared by every dashboard page."""
    offset = max(0, int(top_offset or 0))
    st.markdown(
        f"""
<style>
.dashboard-nav {{ margin:{offset}px 0 14px; width:100%; }}
.dashboard-nav-title {{ font-size:.68rem; font-weight:800; letter-spacing:.06em; margin:7px 0 5px; text-transform:uppercase; color:#9FB0C7; }}
.dashboard-nav-title.s1 {{ color:#7FB3FF; }}
.dashboard-nav-title.s2 {{ color:#FF8F8F; }}
.dashboard-nav-row {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:7px; margin-bottom:7px; }}
.dashboard-nav-row.main {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
.dashboard-nav .stButton {{ width:100%; }}
.dashboard-nav .stButton > button {{ width:100%!important; min-height:40px!important; padding:6px 7px!important; border:1px solid #2b3b57!important; border-radius:9px!important; background:#142036!important; color:#E9F0F8!important; font-size:.73rem!important; font-weight:650!important; line-height:1.1!important; white-space:nowrap!important; }}
.dashboard-nav .s1-row .stButton > button {{ border-color:#2C4E79!important; }}
.dashboard-nav .s2-row .stButton > button {{ border-color:#704044!important; }}
@media(max-width:900px) {{
  .dashboard-nav-row {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
}}
@media(max-width:600px) {{
  .dashboard-nav {{ margin:{offset}px 0 10px; }}
  .dashboard-nav-row,.dashboard-nav-row.main {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:5px; }}
  .dashboard-nav .stButton > button {{ min-height:38px!important; font-size:.66rem!important; padding:5px 4px!important; }}
  .dashboard-nav-title {{ font-size:.62rem; margin:5px 0 4px; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="dashboard-nav">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-nav-title">🏠 MAIN</div>', unsafe_allow_html=True)
        a, b, c = st.columns(3, gap="small")
        with a: _button("🏠 DASHBOARD", "app.py", "nav_home")
        with b: _button("🔵 STRATEGY 1", "pages/current_trading.py", "nav_s1_home")
        with c: _button("🔴 STRATEGY 2", "pages/strategy2.py", "nav_s2_home")

        st.markdown('<div class="dashboard-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
        a, b, c, d, e = st.columns(5, gap="small")
        with a: _button("📌 CURRENT", "pages/current_trading.py", "nav_s1_current")
        with b: _button("📊 ANALYSIS", "pages/analysis.py", "nav_s1_analysis")
        with c: _button("🔎 SCANNER", "pages/stock_scanner.py", "nav_s1_scanner")
        with d: _button("📰 NEWS", "pages/news_analysis.py", "nav_s1_news")
        with e: _button("⬇️ DOWNLOADS", "pages/downloads.py", "nav_s1_downloads")

        st.markdown('<div class="dashboard-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
        a, b, c, d, e = st.columns(5, gap="small")
        with a: _button("📌 CURRENT", "pages/strategy2_current.py", "nav_s2_current")
        with b: _button("📊 ANALYSIS", "pages/strategy2_analysis.py", "nav_s2_analysis")
        with c: _button("🔎 SCANNER", "pages/strategy2_scanner.py", "nav_s2_scanner")
        with d: _button("📰 NEWS", "pages/strategy2_news.py", "nav_s2_news")
        with e: _button("⬇️ DOWNLOADS", "pages/strategy2_downloads.py", "nav_s2_downloads")
        st.markdown('</div>', unsafe_allow_html=True)
