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

# Presentation-only responsive rules. The trading cycle remains controlled by
# config.settings.SCAN_INTERVAL_SECONDS and trading_worker.run_once().
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

# Compatibility guard for older callers that still pass timeout= to
# dhan_data._marketfeed(). This stays at the dashboard boundary and does not
# alter the canonical engine or its data-gating rules.
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
        return _dhan_data._post(
            endpoint,
            {exchange_segment: normalized},
            timeout=max(0.1, float(timeout)),
        )
    _dhan_data._marketfeed = _marketfeed_compat

from config.settings import SCAN_INTERVAL_SECONDS
from dashboard.trading_worker import run_once


@st.fragment(run_every=f"{SCAN_INTERVAL_SECONDS}s")
def _live_trade_worker():
    """Run the canonical paper-trading worker once per refresh interval."""
    result = run_once()
    st.session_state["trade_worker_error"] = None if result.get("ok") else result.get("diagnostics", {}).get("worker_error")


_live_trade_worker()

# Production UI only. Diagnostic/testing modules remain available to CI and
# separate diagnostic pages; the main dashboard does not execute them.
from dashboard.single_master import render_dashboard

render_dashboard()
