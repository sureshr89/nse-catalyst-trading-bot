"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
# single_master.py is the one-page dashboard.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

# Live diagnostic: show 5 real NIFTY 500 constituents from the same verified 500/500 snapshot.
from dashboard.nifty500_sample import render_nifty500_sample
render_nifty500_sample()

# Force the complete Streamlit viewport to the requested black theme.
st.markdown("""
<style>
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stHeader"],
header, main, section {
    background: #000000 !important;
}
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewContainer"] .main {
    background: #000000 !important;
}
[data-testid="stHeader"] { background: #000000 !important; }
[data-testid="stToolbar"] { background: #000000 !important; }
.block-container { background: #000000 !important; }
.label, .value, .sec, .sub, .status,
.stMarkdown, .stMarkdown p, .stCaption, .stCaption p,
.strategy-title, .trade-label, .trade-value {
    color: #ffffff !important;
}
.label { font-size: .62rem !important; }
.value { font-size: 1.02rem !important; }
.sec { font-size: 1.16rem !important; }
.strategy-title { font-size: .92rem !important; }
.state { font-size: .72rem !important; }
.trade-label { font-size: .55rem !important; }
.trade-value { font-size: .76rem !important; }
.sub { font-size: .78rem !important; }
.status { font-size: .79rem !important; }
</style>
""", unsafe_allow_html=True)
