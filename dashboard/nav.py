import streamlit as st


def render_nav(top_offset=0):
    """Render one shared 2x2 navigation that scrolls away with page content."""
    st.markdown(
        f"""
        <style>
        .st-key-nav,.st-key-main_nav,.st-key-nav_grid,.st-key-nav_row_1,.st-key-nav_row_2{{display:none!important;}}
        .st-key-global_nav{{position:relative!important;top:auto!important;left:auto!important;right:auto!important;z-index:1!important;background:transparent!important;padding:0 0 10px!important;margin:{top_offset}px 0 0!important;box-shadow:none!important;}}
        .st-key-global_nav > div[data-testid="stVerticalBlock"]{{max-width:1400px!important;margin:0 auto!important;}}
        .st-key-global_nav [data-testid="stHorizontalBlock"]{{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important;width:100%!important;margin:0 0 8px!important;}}
        .st-key-global_nav [data-testid="stColumn"]{{width:100%!important;min-width:0!important;max-width:none!important;flex:none!important;padding:0!important;}}
        .st-key-global_nav [data-testid="stPageLink"],.st-key-global_nav [data-testid="stPageLink"] a{{width:100%!important;box-sizing:border-box!important;}}
        .st-key-global_nav [data-testid="stPageLink"] a{{min-height:48px!important;display:flex!important;align-items:center!important;justify-content:center!important;padding:8px 6px!important;border:1px solid #2b3b57!important;border-radius:12px!important;background:#142036!important;color:#e9f0f8!important;font-size:.88rem!important;font-weight:700!important;text-decoration:none!important;white-space:nowrap!important;}}
        @media(max-width:768px){{.st-key-global_nav{{padding:0 0 8px!important;margin-top:{top_offset}px!important}}.st-key-global_nav [data-testid="stHorizontalBlock"]{{gap:6px!important;margin-bottom:6px!important}}.st-key-global_nav [data-testid="stPageLink"] a{{min-height:44px!important;font-size:.78rem!important}}}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="global_nav"):
        r1,r2=st.columns(2,gap="small")
        r1.page_link("app.py",label="🟢 BOT STATUS",width="stretch")
        r2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch")
        r3,r4=st.columns(2,gap="small")
        r3.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
        r4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")
