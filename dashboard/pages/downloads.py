from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

# Four navigation buttons, always visible on mobile in a 2x2 grid.
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.7rem .7rem 2rem!important}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:44px!important;padding:.45rem .35rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.76rem!important;font-weight:700!important;text-decoration:none!important}
@media(max-width:768px){[data-testid="stPageLink"] a{min-height:42px!important;font-size:.68rem!important;padding:.35rem .15rem!important}}
</style>
""", unsafe_allow_html=True)

n1,n2=st.columns(2,gap="small")
n3,n4=st.columns(2,gap="small")
n1.page_link("app.py", label="🟢 BOT STATUS", icon="🟢")
n2.page_link("pages/current_trading.py", label="📌 CURRENT TRADING", icon="📌")
n3.page_link("pages/analysis.py", label="📊 ANALYSIS", icon="📊")
n4.page_link("pages/downloads.py", label="⬇️ DOWNLOADS", icon="⬇️")

runpy.run_path(str(ROOT / "pages" / "downloads.py"), run_name="__main__")
