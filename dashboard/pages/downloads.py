from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

st.markdown("""
<style>
[data-testid="stSidebar"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:44px!important;padding:.55rem .4rem!important;border:1px solid #2b3b57!important;border-radius:12px!important;background:#142036!important;color:#e9f0f8!important;font-size:.75rem!important;font-weight:700!important}
@media(max-width:768px){[data-testid="stPageLink"] a{min-height:42px!important;font-size:.62rem!important;padding:.4rem .15rem!important}}
</style>
""", unsafe_allow_html=True)
n1,n2,n3,n4=st.columns(4,gap="small")
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ FILES",icon="⬇️")

runpy.run_path(str(ROOT / "pages" / "downloads.py"), run_name="__main__")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:1rem 1.1rem 2rem!important}
h1{font-size:1.45rem!important;color:#f5f8fc!important}
h2{font-size:1rem!important;color:#dce6f3!important}
[data-testid="stDownloadButton"] button{width:100%!important;min-height:44px!important;border-radius:11px!important;font-size:.8rem!important;font-weight:700!important}
@media(max-width:768px){.block-container{padding:.6rem .5rem 1.5rem!important}h1{font-size:1.2rem!important}h2{font-size:.88rem!important}}
</style>
""", unsafe_allow_html=True)
