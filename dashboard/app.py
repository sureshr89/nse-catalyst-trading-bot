"""NSE Catalyst Streamlit entry point.

The page does not auto-refresh. Live 500-stock data is handled by the existing
breadth engine. The slow optional NIFTY 500 index quote must never block app startup.
"""
from pathlib import Path
import runpy
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

# The 500-stock Dhan feed is the important data path. The optional index quote
# can make startup wait on a second marketfeed request and historical fallback.
# Never let that optional request hold the whole dashboard hostage.
try:
    import market.nifty500_breadth as _breadth_module
    _breadth_module.index_quote = lambda *args, **kwargs: None
except Exception:
    pass

_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(
        str(ROOT / "dashboard" / "single_master.py"),
        run_name="__nse_catalyst_dashboard__",
    )
    from dashboard.enhancements import render_enhancements
    render_enhancements()
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
finally:
    st.set_page_config = _original_set_page_config
