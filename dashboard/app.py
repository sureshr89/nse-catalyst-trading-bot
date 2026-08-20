"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import sys
import requests

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


def _index_from_yahoo(symbol):
    """Best-effort latest index quote for indices not available in Dhan's NSE IDX_I feed."""
    try:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "1d", "interval": "1m", "includePrePost": "false"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json().get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        previous = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None or previous in (None, 0):
            return None
        price = float(price)
        previous = float(previous)
        return {"value": price, "change_pct": (price - previous) / previous * 100.0}
    except Exception:
        return None


def _dhan_index(index_name):
    try:
        from market.dhan_data import configured, index_quote
        if not configured():
            return None
        quote = index_quote(index_name)
        if not quote:
            return None
        return {"value": float(quote["LTP"]), "change_pct": float(quote["change_pct"])}
    except Exception:
        return None


def _index_card(label, quote):
    if quote is None:
        value = "WAITING"
        change = "—"
        cls = "index-neutral"
    else:
        value = f"{quote['value']:,.2f}"
        change_pct = quote["change_pct"]
        if change_pct > 0:
            change = f"▲ {change_pct:.2f}%"
            cls = "index-positive"
        elif change_pct < 0:
            change = f"▼ {abs(change_pct):.2f}%"
            cls = "index-negative"
        else:
            change = "• 0.00%"
            cls = "index-neutral"
    return f'''<div class="market-index-card">
        <div class="market-index-label">{label}</div>
        <div class="market-index-value">{value}</div>
        <div class="market-index-change {cls}">{change}</div>
    </div>'''


@st.fragment(run_every="15s")
def _market_indices_header():
    nifty = _dhan_index("NIFTY 50") or _index_from_yahoo("^NSEI")
    banknifty = _dhan_index("NIFTY BANK") or _index_from_yahoo("^NSEBANK")
    sensex = _index_from_yahoo("^BSESN")
    dow = _index_from_yahoo("^DJI")

    st.markdown("""
    <style>
    .market-index-wrap{background:#17110d;padding:8px 0 16px;border-radius:18px}
    .market-index-hero{background:#1d2025;border:1px solid #515862;border-radius:30px;padding:24px 28px;margin:0 0 18px;box-shadow:0 8px 28px rgba(0,0,0,.22)}
    .market-index-title{display:flex;align-items:center;gap:18px;font-size:clamp(1.8rem,4vw,3.2rem);font-weight:900;color:#f1f1ff;letter-spacing:-.03em}
    .market-index-icon{width:74px;height:74px;display:flex;align-items:center;justify-content:center;border:2px solid #555b64;border-radius:22px;background:#090b0e;font-size:2.45rem;flex:0 0 auto}
    .market-index-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:0 38px}
    .market-index-card{background:#1d1f24;border:1px solid #555a62;border-radius:28px;min-height:210px;padding:32px 28px 26px;box-shadow:0 5px 18px rgba(0,0,0,.16)}
    .market-index-label{font-size:1.55rem;font-weight:850;color:#8198bb;letter-spacing:.01em;margin-bottom:22px}
    .market-index-value{font-size:2.05rem;line-height:1.05;font-weight:900;color:#f2f2ff;margin-bottom:26px}
    .market-index-change{display:inline-flex;align-items:center;border-radius:28px;padding:10px 22px;font-size:1.25rem;font-weight:850;min-width:165px;justify-content:center}
    .index-positive{color:#49cf83;background:#10271d;border:1px solid #3e664e}
    .index-negative{color:#ff826b;background:#2b1b19;border:1px solid #79534d}
    .index-neutral{color:#c7ccd4;background:#24262a;border:1px solid #565a61}
    @media(max-width:700px){.market-index-grid{grid-template-columns:1fr;padding:0 4px}.market-index-card{min-height:170px;padding:24px 20px}.market-index-label{font-size:1.2rem}.market-index-value{font-size:1.75rem}.market-index-change{font-size:1rem;min-width:130px}.market-index-hero{border-radius:22px;padding:18px}.market-index-icon{width:58px;height:58px;font-size:1.9rem}.market-index-title{font-size:1.8rem}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="market-index-wrap"><div class="market-index-hero"><div class="market-index-title"><span class="market-index-icon">⚖️</span><span>Market Indices</span></div></div><div class="market-index-grid">' +
                ''.join([
                    _index_card("SENSEX", sensex),
                    _index_card("NIFTY", nifty),
                    _index_card("BANKNIFTY", banknifty),
                    _index_card("DOW JONES", dow),
                ]) +
                '</div></div>', unsafe_allow_html=True)


_market_indices_header()

# Render the original dashboard after the new market-indices header. Its market
# alignment, S1-S5 and journal remain functionally unchanged. Its old download/tip
# blocks are intercepted only so this entrypoint can place them exactly where requested.
_original_markdown = st.markdown
_original_download_button = st.download_button
_original_caption = st.caption


def _master_markdown_filter(body, *args, **kwargs):
    text = body if isinstance(body, str) else str(body)
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

try:
    from dashboard.test_tab import render_test_tab
    st.divider()
    render_test_tab()
except Exception as exc:
    st.error(f"TEST trade unavailable: {type(exc).__name__}: {exc}")

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

st.markdown("""
<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],[data-testid="stHeader"],header,main,section{background:#17110d!important}
.block-container{background:#17110d!important}
.stMarkdown,.stMarkdown p,.stCaption,.stCaption p{color:#fff!important}
.tip-final{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:13px;font-weight:700;color:#fff}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
st.markdown('<div class="tip-final">💡 One disciplined trade is better than many emotional trades.</div>', unsafe_allow_html=True)
