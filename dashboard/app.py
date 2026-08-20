"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as _engine_main

# Keep diagnostics optional so a diagnostic-module/import problem can NEVER stop
# the master dashboard from loading.
try:
    from dashboard.trade_path_diagnostics import capture as capture_trade_path, render as render_trade_path
    _DIAGNOSTICS_IMPORT_ERROR = None
except Exception as exc:
    _DIAGNOSTICS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

    def capture_trade_path(*args, **kwargs):
        return None

    def render_trade_path():
        st.info("Trade-path diagnostics are temporarily unavailable; the master dashboard is still running.")


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

# Keep the original master dashboard. Additional diagnostics/test content is
# appended after it without changing S1-S5.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

# Do not render the old five-stock sample here. It duplicated live data after
# the dashboard's trading tip.
render_trade_path()

# Separate isolated TEST trade. It does not alter normal S1-S5 state.
st.divider()
st.markdown("### 🧪 TEST TRADE")
st.caption("One isolated paper test trade • no journal • no win/loss • S1–S5 unchanged")
try:
    from dashboard.test_tab import render_test_tab
    render_test_tab()
except Exception as exc:
    st.error(f"TEST trade unavailable: {type(exc).__name__}: {exc}")

# One and only one DAILY TRADING TIP, at the very end of the page.
st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#000!important}
.block-container{background:#000!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
/* Hide the legacy tip block and its preceding heading from single_master.py. */
.tip{display:none!important}
[data-testid="stElementContainer"]:has(+ [data-testid="stElementContainer"] .tip){display:none!important}
.tip-final{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:13px;font-weight:700;color:#fff}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
st.markdown('<div class="tip-final">💡 One disciplined trade is better than many emotional trades.</div>', unsafe_allow_html=True)
