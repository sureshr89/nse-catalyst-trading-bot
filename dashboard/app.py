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

# Render the original dashboard first. Its market alignment, S1-S5 and journal
# remain visually unchanged. Its old download/tip blocks are intercepted only
# so this entrypoint can place them exactly where requested below.
_original_markdown = st.markdown
_original_download_button = st.download_button
_original_caption = st.caption


def _master_markdown_filter(body, *args, **kwargs):
    text = body if isinstance(body, str) else str(body)
    # Defer the old cumulative-download heading and legacy daily-tip elements.
    if "MASTER DOWNLOAD — CUMULATIVE" in text:
        return None
    if '<div class="sec">💡 DAILY TRADING TIP</div>' in text:
        return None
    if '<div class="tip">' in text:
        return None
    return _original_markdown(body, *args, **kwargs)


def _master_download_filter(*args, **kwargs):
    return None


def _master_caption_filter(*args, **kwargs):
    # The only captions in single_master are attached to the deferred download
    # and the trailing legacy footer, so both are intentionally deferred.
    return None


st.markdown = _master_markdown_filter
st.download_button = _master_download_filter
st.caption = _master_caption_filter
try:
    runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")
finally:
    st.markdown = _original_markdown
    st.download_button = _original_download_button
    st.caption = _original_caption

# Exact page order from here: Journal (inside the original dashboard) ->
# Trade Path -> Test Trade -> Master Download -> Daily Trading Tip.
render_trade_path()

# Isolated TEST trade only. It never changes S1-S5 or the journal.
try:
    from dashboard.test_tab import render_test_tab
    st.divider()
    render_test_tab()
except Exception as exc:
    st.error(f"TEST trade unavailable: {type(exc).__name__}: {exc}")

# Single cumulative download, immediately after TEST TRADE.
st.markdown('<div class="sec">📥 MASTER DOWNLOAD — CUMULATIVE</div>', unsafe_allow_html=True)
try:
    master_csv = _engine_main.MasterEngine().read_trades() if hasattr(_engine_main.MasterEngine, "read_trades") else None
except Exception:
    master_csv = None

try:
    import pandas as pd
    _master_path = ROOT / "outputs" / "trades.csv"
    _master_df = pd.read_csv(_master_path) if _master_path.exists() else pd.DataFrame()
except Exception:
    _master_df = pd.DataFrame()

st.download_button(
    "⬇️ Download Master CSV",
    _master_df.to_csv(index=False).encode("utf-8"),
    "nse_catalyst_master.csv",
    "text/csv",
    use_container_width=True,
    key="master_csv_final",
)
st.caption(f"Cumulative journal: {len(_master_df)} trade record(s). Original journal columns preserved.")

# One and only one DAILY TRADING TIP, at the absolute end of the page.
st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#000!important}
.block-container{background:#000!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
.tip-final{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:13px;font-weight:700;color:#fff}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
st.markdown('<div class="tip-final">💡 One disciplined trade is better than many emotional trades.</div>', unsafe_allow_html=True)
