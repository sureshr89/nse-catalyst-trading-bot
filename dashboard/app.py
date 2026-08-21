"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import sys
import inspect

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
# substantially more readable on small screens. These rules intentionally
# affect presentation only; they do not change the trading engine or its
# 15-second cycle.
st.markdown("""
<style>
@media (max-width: 700px) {
    div[style*="font-size:8px"] { font-size: 11px !important; line-height: 1.25 !important; }
    div[style*="font-size:12px"] { font-size: 15px !important; line-height: 1.25 !important; }
    div[style*="font-size:17px"] { font-size: 21px !important; }
    div[style*="font-size:9px"] { font-size: 11px !important; line-height: 1.25 !important; }
    span[style*="font-size:20px"] { font-size: 24px !important; }
    div[style*="grid-template-columns:repeat(auto-fit,minmax(125px"] {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px !important;
    }
    div[style*="border-top:3px solid"] { padding: 14px 13px !important; }
}
</style>
""", unsafe_allow_html=True)

# Compatibility guard: older engine code may call _marketfeed(..., timeout=...).
# The current adapter routes through _post(), so accept the legacy timeout
# argument here as well. This prevents a stale imported caller from blocking
# the live 15-second collection cycle during deployment transitions.
from market import dhan_data as _dhan_data
try:
    _marketfeed_params = inspect.signature(_dhan_data._marketfeed).parameters
except (AttributeError, TypeError, ValueError):
    _marketfeed_params = {}
if "timeout" not in _marketfeed_params:
    def _marketfeed_compat(exchange_segment, security_ids, endpoint="/marketfeed/ohlc", timeout=15):
        normalized = []
        for value in list(security_ids)[:1000]:
            try:
                number = float(value)
                if number.is_integer():
                    normalized.append(int(number))
            except (TypeError, ValueError, OverflowError):
                continue
        if not normalized:
            return {}
        return _dhan_data._post(endpoint, {exchange_segment: normalized}, timeout=max(0.1, float(timeout)))
    _dhan_data._marketfeed = _marketfeed_compat

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
