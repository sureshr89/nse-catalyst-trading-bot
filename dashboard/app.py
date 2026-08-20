"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import streamlit as st
import main as _engine_main

ROOT = Path(__file__).resolve().parents[1]

@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()

@st.fragment(run_every="15s")
def _live_trade_worker():
    """Run the paper-trading engine every 15 seconds; never place live orders."""
    try:
        _get_trading_engine().run_cycle()
    except Exception as exc:
        st.session_state["trade_worker_error"] = f"{type(exc).__name__}: {exc}"

_live_trade_worker()
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

from dashboard.nifty500_sample import render_nifty500_sample
render_nifty500_sample()

from dashboard.execution_status import render_execution_status
render_execution_status()

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#000!important}
.block-container{background:#000!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
</style>
""", unsafe_allow_html=True)
