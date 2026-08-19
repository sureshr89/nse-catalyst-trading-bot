import streamlit as st

def _link(label,page): st.page_link(page,label=label)
def _row(items):
    cols=st.columns(len(items),gap="small")
    for col,(label,page) in zip(cols,items):
        with col:_link(label,page)

def render_nav(top_offset=0):
    if top_offset: st.write("");st.write("")
    st.markdown("""
    <style>
    .nse-nav-title{font-size:.78rem;font-weight:800;letter-spacing:.06em;margin:8px 0 7px;text-transform:uppercase;color:#A9B7CA}
    [data-testid="stPageLink"]{width:100%!important;margin:0!important}
    [data-testid="stPageLink"] a{width:100%!important;min-height:46px!important;border:1px solid #30425F!important;border-radius:11px!important;background:#111B2D!important;padding:6px 4px!important;box-sizing:border-box!important;display:flex!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis}
    [data-testid="stPageLink"] a:hover{border-color:#59769F!important;background:#192943!important}
    [data-testid="stPageLink"] a p{overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;margin:0!important;font-weight:750!important}
    @media(max-width:900px){[data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important}[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:auto!important;min-width:0!important}}
    @media(max-width:600px){[data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))!important}[data-testid="stPageLink"] a{min-height:44px!important;font-size:.74rem!important}}
    </style>
    """,unsafe_allow_html=True)
    st.markdown('<div class="nse-nav-title">🏠 STRATEGIES</div>',unsafe_allow_html=True)
    _row([("🔵 STRATEGY 1","pages/current_trading.py"),("🔴 STRATEGY 2","pages/strategy2_current.py"),("🟢 STRATEGY 3","pages/strategy3_current.py"),("🟣 STRATEGY 4","pages/strategy4_current.py"),("🟠 STRATEGY 5","pages/strategy5_current.py")])
