"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import streamlit as st
import main as _engine_main
from dashboard.trade_path_diagnostics import capture as capture_trade_path, render as render_trade_path

ROOT = Path(__file__).resolve().parents[1]

@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()

@st.fragment(run_every="15s")
def _live_trade_worker():
    """Run exactly one normal paper-trading engine cycle every 15 seconds."""
    try:
        engine = _get_trading_engine()
        result = engine.run_cycle()
        capture_trade_path(engine, result)
        st.session_state["trade_worker_error"] = None
    except Exception as exc:
        try:
            engine = _get_trading_engine()
            capture_trade_path(engine, [], exc)
        except Exception:
            pass
        st.session_state["trade_worker_error"] = f"{type(exc).__name__}: {exc}"

_live_trade_worker()
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

# This reports the result of the SAME engine cycle; it never executes a second trade.
render_trade_path()

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