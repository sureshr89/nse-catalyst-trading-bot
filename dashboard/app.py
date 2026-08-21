"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="NSE Catalyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Keep the dashboard structure unchanged, but make the existing strategy cards
# substantially more readable on small screens.  These rules intentionally
# affect presentation only; they do not change the trading engine or its
# 15-second cycle.
st.markdown("""
<style>
@media (max-width: 700px) {
    /* Strategy card labels/values */
    div[style*="font-size:8px"] {
        font-size: 11px !important;
        line-height: 1.25 !important;
    }
    div[style*="font-size:12px"] {
        font-size: 15px !important;
        line-height: 1.25 !important;
    }
    div[style*="font-size:17px"] {
        font-size: 21px !important;
    }
    div[style*="font-size:9px"] {
        font-size: 11px !important;
        line-height: 1.25 !important;
    }
    span[style*="font-size:20px"] {
        font-size: 24px !important;
    }

    /* Keep the strategy details as two comfortable columns on phones. */
    div[style*="grid-template-columns:repeat(auto-fit,minmax(125px"] {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px !important;
    }

    /* Slightly more breathing room inside cards. */
    div[style*="border-top:3px solid"] {
        padding: 14px 13px !important;
    }
}
</style>
""", unsafe_allow_html=True)

import main as _engine_main
from config.settings import SCAN_INTERVAL_SECONDS


@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()


@st.fragment(run_every=f"{SCAN_INTERVAL_SECONDS}s")
def _live_trade_worker():
    """Run one fresh 15s-collection + 10s-decision production cycle."""
    try:
        engine = _get_trading_engine()
        engine.run_cycle()
        st.session_state["trade_worker_error"] = None
    except Exception as exc:
        st.session_state["trade_worker_error"] = f"{type(exc).__name__}: {exc}"


_live_trade_worker()

# Production UI only. Diagnostic/testing files remain available to CI but are
# intentionally not rendered in the live trading dashboard.
from dashboard.single_master import render_dashboard

render_dashboard()
