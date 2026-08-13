from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / "pages" / "current.py"), run_name="__main__")

# Final visual layer: compact cards, readable tables and mobile-friendly spacing.
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:1rem 1.1rem 2rem!important}
h1{font-size:1.45rem!important;line-height:1.2!important;color:#f5f8fc!important}
h2{font-size:1rem!important;color:#dce6f3!important;margin-top:1rem!important}
h3{font-size:.9rem!important;color:#dce6f3!important}
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:12px!important;padding:.55rem .7rem!important;min-height:76px!important}
[data-testid="stMetricLabel"]{font-size:.68rem!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:1.1rem!important;color:#f4f7fb!important;font-weight:700!important}
[data-testid="stDataFrame"]{border:1px solid #26344d!important;border-radius:10px!important;overflow:hidden!important}
.stAlert{border-radius:10px!important}
@media(max-width:768px){.block-container{padding:.6rem .5rem 1.5rem!important}h1{font-size:1.2rem!important}h2{font-size:.86rem!important}[data-testid="stMetric"]{min-height:64px!important;padding:.42rem .48rem!important}[data-testid="stMetricValue"]{font-size:.95rem!important}[data-testid="stMetricLabel"]{font-size:.61rem!important}}
</style>
""", unsafe_allow_html=True)
