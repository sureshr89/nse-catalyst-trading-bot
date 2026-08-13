from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
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
