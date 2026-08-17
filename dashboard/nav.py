import streamlit as st


def render_nav(top_offset=0):
    """Clear grouped navigation. Strategy 1 and Strategy 2 never share page links."""
    offset = max(0, int(top_offset or 0))
    st.markdown(f'''<style>
.st-key-global_nav{{position:relative!important;margin:{offset}px 0 12px!important;padding:0!important;width:100%!important}}
.st-key-global_nav .nav-title{{font-size:.70rem;font-weight:800;letter-spacing:.06em;color:#9FB0C7;margin:7px 0 5px;text-transform:uppercase}}
.st-key-global_nav .nav-s1{{color:#7FB3FF!important}}
.st-key-global_nav .nav-s2{{color:#FF8F8F!important}}
.st-key-global_nav [data-testid="stHorizontalBlock"]{{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;width:100%!important;gap:7px!important;margin:0 0 6px!important}}
.st-key-global_nav [data-testid="stColumn"]{{display:block!important;min-width:0!important;padding:0!important;flex:1 1 0!important}}
.st-key-global_nav [data-testid="stButton"]{{width:100%!important}}
.st-key-global_nav [data-testid="stButton"] button{{width:100%!important;min-height:40px!important;border:1px solid #2b3b57!important;border-radius:9px!important;background:#142036!important;color:#E9F0F8!important;font-size:.75rem!important;font-weight:650!important;line-height:1.15!important;white-space:nowrap!important;padding:6px 4px!important}}
.st-key-global_nav .nav-s1-row [data-testid="stButton"] button{{border-color:#2C4E79!important}}
.st-key-global_nav .nav-s2-row [data-testid="stButton"] button{{border-color:#704044!important}}
@media(max-width:768px){{
.st-key-global_nav{{margin:{offset}px 0 10px!important}}
.st-key-global_nav [data-testid="stHorizontalBlock"]{{gap:5px!important;margin-bottom:5px!important}}
.st-key-global_nav [data-testid="stButton"] button{{min-height:39px!important;font-size:.67rem!important;padding:5px 3px!important}}
.st-key-global_nav .nav-title{{font-size:.64rem;margin:6px 0 4px}}
}}
</style>''', unsafe_allow_html=True)

    with st.container(key="global_nav"):
        st.markdown("<div class='nav-title'>🏠 MAIN</div>", unsafe_allow_html=True)
        a, b, c = st.columns(3, gap="small")
        with a:
            if st.button("🏠 DASHBOARD", key="global_nav_home", width="stretch"):
                st.switch_page("app.py")
        with b:
            if st.button("🔵 STRATEGY 1", key="global_nav_s1home", width="stretch"):
                st.switch_page("pages/current_trading.py")
        with c:
            if st.button("🔴 STRATEGY 2", key="global_nav_s2home", width="stretch"):
                st.switch_page("pages/strategy2.py")

        st.markdown("<div class='nav-title nav-s1'>🔵 STRATEGY 1 — PDH/PDL RETURN</div>", unsafe_allow_html=True)
        with st.container(key="nav_s1_row"):
            a, b, c = st.columns(3, gap="small")
            with a:
                if st.button("📌 CURRENT", key="global_nav_s1_current", width="stretch"):
                    st.switch_page("pages/current_trading.py")
            with b:
                if st.button("📊 ANALYSIS", key="global_nav_s1_analysis", width="stretch"):
                    st.switch_page("pages/analysis.py")
            with c:
                if st.button("🔎 SCANNER", key="global_nav_s1_scanner", width="stretch"):
                    st.switch_page("pages/stock_scanner.py")
            a, b, c = st.columns(3, gap="small")
            with a:
                if st.button("📰 NEWS", key="global_nav_s1_news", width="stretch"):
                    st.switch_page("pages/news_analysis.py")
            with b:
                if st.button("⬇️ DOWNLOADS", key="global_nav_s1_downloads", width="stretch"):
                    st.switch_page("pages/downloads.py")
            with c:
                st.empty()

        st.markdown("<div class='nav-title nav-s2'>🔴 STRATEGY 2 — GAP-UP EXTENSION SELL</div>", unsafe_allow_html=True)
        with st.container(key="nav_s2_row"):
            a, b, c = st.columns(3, gap="small")
            with a:
                if st.button("📌 CURRENT", key="global_nav_s2_current", width="stretch"):
                    st.switch_page("pages/strategy2_current.py")
            with b:
                if st.button("📊 ANALYSIS", key="global_nav_s2_analysis", width="stretch"):
                    st.switch_page("pages/strategy2_analysis.py")
            with c:
                if st.button("🔎 SCANNER", key="global_nav_s2_scanner", width="stretch"):
                    st.switch_page("pages/strategy2_scanner.py")
            a, b, c = st.columns(3, gap="small")
            with a:
                if st.button("📰 NEWS", key="global_nav_s2_news", width="stretch"):
                    st.switch_page("pages/strategy2_news.py")
            with b:
                if st.button("⬇️ DOWNLOADS", key="global_nav_s2_downloads", width="stretch"):
                    st.switch_page("pages/strategy2_downloads.py")
            with c:
                st.empty()
