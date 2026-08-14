import streamlit as st

def render_nav(top_offset=0):
    """Shared 2x2 navigation, always rendered at the top of the page."""
    st.markdown('''<style>
.st-key-global_nav{position:relative!important;margin:0 0 12px!important;padding:0!important;width:100%!important}
.st-key-global_nav [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;width:100%!important;gap:10px!important;margin:0 0 10px!important}
.st-key-global_nav [data-testid="stColumn"]{display:block!important;width:calc(50% - 5px)!important;min-width:0!important;max-width:calc(50% - 5px)!important;flex:0 0 calc(50% - 5px)!important;padding:0!important}
.st-key-global_nav [data-testid="stButton"]{width:100%!important}
.st-key-global_nav [data-testid="stButton"] button{width:100%!important;min-height:44px!important;border:1px solid #2b3b57!important;border-radius:10px!important;background:#142036!important;color:#e9f0f8!important;font-size:.82rem!important;font-weight:650!important;line-height:1.15!important;white-space:nowrap!important;padding:7px 5px!important}
@media(max-width:768px){.st-key-global_nav{margin:0 0 10px!important}.st-key-global_nav [data-testid="stHorizontalBlock"]{gap:7px!important;margin-bottom:7px!important}.st-key-global_nav [data-testid="stColumn"]{width:calc(50% - 3.5px)!important;max-width:calc(50% - 3.5px)!important;flex:0 0 calc(50% - 3.5px)!important}.st-key-global_nav [data-testid="stButton"] button{min-height:42px!important;font-size:.72rem!important;font-weight:650!important}}
</style>''',unsafe_allow_html=True)
    with st.container(key="global_nav"):
        r1,r2=st.columns(2,gap="small")
        with r1:
            if st.button("🟢 BOT STATUS",key="global_nav_bot",use_container_width=True):st.switch_page("app.py")
        with r2:
            if st.button("📌 CURRENT TRADING",key="global_nav_current",use_container_width=True):st.switch_page("pages/current_trading.py")
        r3,r4=st.columns(2,gap="small")
        with r3:
            if st.button("📊 ANALYSIS",key="global_nav_analysis",use_container_width=True):st.switch_page("pages/analysis.py")
        with r4:
            if st.button("⬇️ DOWNLOADS",key="global_nav_downloads",use_container_width=True):st.switch_page("pages/downloads.py")
