"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

# Install the same Dhan/data-alignment patches used by the trading engine.
# Importing main.py does not render the dashboard; it only installs the patches.
import main as _engine_main

@st.cache_resource(show_spinner=False)
def _get_trading_engine():
    return _engine_main.MasterEngine()

@st.fragment(run_every="15s")
def _live_trade_worker():
    """Actually run the paper-trading engine on every live refresh cycle.

    The dashboard previously only displayed signals.csv/trades.csv. That meant
    the Streamlit app could show perfect market data forever without ever
    invoking MasterEngine.run_cycle(). This fragment is the missing execution
    loop. It remains paper-only because LIVE_TRADING is hard-disabled in config.
    """
    try:
        engine = _get_trading_engine()
        engine.run_cycle()
    except Exception as exc:
        # Do not crash the dashboard; the engine writes its own diagnostics.
        st.session_state["trade_worker_error"] = f"{type(exc).__name__}: {exc}"

# Register the live worker before rendering the dashboard. Streamlit fragments
# rerun independently, so the trading cycle continues every 15 seconds.
_live_trade_worker()

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
