import streamlit as st


def _link(label, page):
    # st.page_link does not support a key parameter.
    st.page_link(page, label=label)


def _row(left, right):
    with st.container(
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
        gap="small",
        width="stretch",
    ):
        _link(left[0], left[1])
        _link(right[0], right[1])


def render_nav(top_offset=0):
    """Clean 2x2 native Streamlit navigation. News is intentionally absent."""
    offset = max(0, int(top_offset or 0))
    if offset:
        st.write("")
        st.write("")

    st.markdown(
        """
        <style>
        .nse-nav-title {
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .05em;
            margin: 8px 0 6px;
            text-transform: uppercase;
        }
        .nse-nav-title.main { color: #A9B7CA; }
        .nse-nav-title.s1 { color: #79B4FF; }
        .nse-nav-title.s2 { color: #FF9292; }
        [data-testid="stPageLink"] a {
            min-height: 52px !important;
            border: 1px solid #303A4B !important;
            border-radius: 12px !important;
            background: #151B26 !important;
            padding: 8px 10px !important;
            box-sizing: border-box !important;
            justify-content: center !important;
        }
        [data-testid="stPageLink"] a:hover {
            border-color: #59769F !important;
            background: #192233 !important;
        }
        @media (max-width: 600px) {
            [data-testid="stPageLink"] a {
                min-height: 50px !important;
                padding: 7px 5px !important;
                font-size: .76rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="nse-nav-title main">🏠 MAIN</div>', unsafe_allow_html=True)
    _row(("🔵 STRATEGY 1", "pages/current_trading.py"), ("🔴 STRATEGY 2", "pages/strategy2.py"))

    st.markdown('<div class="nse-nav-title s1">🔵 STRATEGY 1 — PDH/PDL RETURN</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT", "pages/current_trading.py"), ("📊 ANALYSIS", "pages/analysis.py"))
    _row(("🔎 SCANNER", "pages/stock_scanner.py"), ("⬇️ DOWNLOADS", "pages/downloads.py"))

    st.markdown('<div class="nse-nav-title s2">🔴 STRATEGY 2 — GAP EXTENSION REVERSAL</div>', unsafe_allow_html=True)
    _row(("📌 CURRENT", "pages/strategy2_current.py"), ("📊 ANALYSIS", "pages/strategy2_analysis.py"))
    _row(("🔎 SCANNER", "pages/strategy2_scanner.py"), ("⬇️ DOWNLOADS", "pages/strategy2_downloads.py"))
