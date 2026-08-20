"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as _engine_main

try:
    from dashboard.trade_path_diagnostics import capture as capture_trade_path, render as render_trade_path
except Exception:
    def capture_trade_path(*args, **kwargs):
        return None
    def render_trade_path():
        return None


@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()


@st.fragment(run_every="15s")
def _live_trade_worker():
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

# Main dashboard owns the market data, S1-S5, cumulative download and journal.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

# Diagnostics are supplementary and appear after the main dashboard.
render_trade_path()

# Isolated TEST trade only. It never changes S1-S5 or the journal.
try:
    from dashboard.test_tab import render_test_tab
    st.divider()
    render_test_tab()
except Exception as exc:
    st.error(f"TEST trade unavailable: {type(exc).__name__}: {exc}")

# The main dashboard already renders MASTER DOWNLOAD — CUMULATIVE.
# Do not render another copy here.

# The main dashboard's legacy tip is hidden; this is the single final tip.
st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#000!important}
.block-container{background:#000!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
/* Remove the legacy tip, its heading, and its trailing refresh caption. */
[data-testid="stElementContainer"]:has(.tip){display:none!important}
[data-testid="stElementContainer"]:has(+ [data-testid="stElementContainer"] .tip){display:none!important}
[data-testid="stElementContainer"]:has(.tip) + [data-testid="stElementContainer"]{display:none!important}
.tip{display:none!important}
.tip-final{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:13px;font-weight:700;color:#fff}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
st.markdown('<div class="tip-final">💡 One disciplined trade is better than many emotional trades.</div>', unsafe_allow_html=True)
