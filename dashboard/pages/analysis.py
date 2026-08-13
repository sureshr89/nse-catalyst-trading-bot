"""Streamlit page entrypoint for the read-only trading analysis."""
from pathlib import Path
import runpy
import streamlit as st

ANALYSIS_FILE = Path(__file__).resolve().parent.parent / "analysis.py"
runpy.run_path(str(ANALYSIS_FILE), run_name="__main__")

# Final presentation layer applied after the research page renders.
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:1rem 1.1rem 2rem!important}
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:12px!important;padding:.55rem .7rem!important;min-height:78px!important}
[data-testid="stMetricLabel"]{font-size:.68rem!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:1.1rem!important;color:#f4f7fb!important;font-weight:700!important}
.analysis-title{font-size:1.45rem!important;line-height:1.2!important;color:#f5f8fc!important}
.analysis-subtitle{font-size:.74rem!important;color:#9fb0c7!important;line-height:1.45!important}
.section-title{font-size:.9rem!important;color:#dce6f3!important;margin-top:1rem!important}
[data-testid="stDataFrame"]{border:1px solid #26344d!important;border-radius:10px!important;overflow:hidden!important}
.js-plotly-plot{border:1px solid #26344d;border-radius:12px;padding:2px;background:#111b2d}
@media(max-width:768px){.block-container{padding:.6rem .5rem 1.5rem!important}.analysis-title{font-size:1.18rem!important}.analysis-subtitle{font-size:.67rem!important}[data-testid="stMetric"]{min-height:64px!important;padding:.42rem .48rem!important}[data-testid="stMetricValue"]{font-size:.95rem!important}}
</style>
""", unsafe_allow_html=True)
