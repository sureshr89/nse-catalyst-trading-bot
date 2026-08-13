import streamlit as st


def render_nav():
    """Render one shared fixed 2x2 navigation on every dashboard page."""
    st.markdown(
        """
        <style>
        /* Remove all older page-specific navigation blocks. */
        .st-key-nav,
        .st-key-main_nav,
        .st-key-nav_grid,
        .st-key-nav_row_1,
        .st-key-nav_row_2 { display:none!important; }

        /* ONE navigation only: fixed so all four buttons stay visible together. */
        .st-key-global_nav {
            position:fixed!important;
            top:64px!important;
            left:0!important;
            right:0!important;
            z-index:999999!important;
            background:#0b1220!important;
            padding:8px 10px 9px!important;
            margin:0!important;
            box-sizing:border-box!important;
            box-shadow:0 3px 12px rgba(0,0,0,.30)!important;
        }
        .st-key-global_nav > div[data-testid="stVerticalBlock"] {
            max-width:1400px!important;
            margin:0 auto!important;
        }
        .st-key-global_nav [data-testid="stHorizontalBlock"] {
            display:grid!important;
            grid-template-columns:repeat(2,minmax(0,1fr))!important;
            gap:7px!important;
            width:100%!important;
            margin:0!important;
        }
        .st-key-global_nav [data-testid="stColumn"] {
            width:100%!important;
            min-width:0!important;
            max-width:none!important;
            flex:none!important;
            padding:0!important;
        }
        .st-key-global_nav [data-testid="stPageLink"],
        .st-key-global_nav [data-testid="stPageLink"] a {width:100%!important;box-sizing:border-box!important}
        .st-key-global_nav [data-testid="stPageLink"] a {
            min-height:43px!important;
            display:flex!important;
            align-items:center!important;
            justify-content:center!important;
            padding:6px 4px!important;
            border:1px solid #2b3b57!important;
            border-radius:11px!important;
            background:#142036!important;
            color:#e9f0f8!important;
            font-size:.66rem!important;
            font-weight:700!important;
            text-decoration:none!important;
            white-space:nowrap!important;
        }
        /* Keep page content below the fixed navigation. */
        .st-key-global_nav + div { min-height:104px!important; }

        /* All Plotly charts are display-only: no pinch, zoom, pan or drag. */
        .js-plotly-plot,
        [data-testid="stPlotlyChart"],
        [data-testid="stPlotlyChart"] * {
            pointer-events:none!important;
            touch-action:none!important;
        }

        @media(max-width:768px){
            .st-key-global_nav{top:64px!important;padding:7px 7px 8px!important}
            .st-key-global_nav [data-testid="stHorizontalBlock"]{gap:6px!important}
            .st-key-global_nav [data-testid="stPageLink"] a{min-height:42px!important;font-size:.60rem!important}
            .st-key-global_nav + div{min-height:101px!important}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="global_nav"):
        r1, r2 = st.columns(2, gap="small")
        r1.page_link("app.py", label="🟢 BOT STATUS", width="stretch")
        r2.page_link("pages/current_trading.py", label="📌 CURRENT TRADING", width="stretch")
        r3, r4 = st.columns(2, gap="small")
        r3.page_link("pages/analysis.py", label="📊 ANALYSIS", width="stretch")
        r4.page_link("pages/downloads.py", label="⬇️ DOWNLOADS", width="stretch")
