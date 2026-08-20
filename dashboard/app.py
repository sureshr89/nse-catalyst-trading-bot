"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as _engine_main
from dashboard.trade_path_diagnostics import capture as capture_trade_path, render as render_trade_path


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

# KEEP THE ORIGINAL MASTER DASHBOARD. The TEST section is appended at the very
# bottom of the same page so it cannot alter or replace the existing layout.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

from dashboard.nifty500_sample import render_nifty500_sample
render_nifty500_sample()
render_trade_path()

# Separate read-only TEST section at the very bottom. It does not create,
# execute, store, journal, or score any trade and does not affect S1-S5.
st.divider()
st.markdown("### 🧪 TEST — Live Data / Entry Check")
st.caption("READ-ONLY TEST • no signals • no trades • no journal • no win/loss • S1–S5 unchanged")
from dashboard.test_tab import render_test_tab
render_test_tab()

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#000!important}
.block-container{background:#000!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
</style>
""", unsafe_allow_html=True)
