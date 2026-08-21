"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import re
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

# The dashboard must display the same market snapshot used by the production
# MasterEngine.  This bridge deliberately changes no visual component: it only
# replaces the legacy breadth snapshot source with the canonical engine snapshot.
def _canonical_breadth_snapshot(force=False):
    try:
        engine = _get_trading_engine()
        snap = engine._market_snapshot()
        prices = snap.get("prices")
        coverage = len(prices) if hasattr(prices, "__len__") else 0
        sector = snap.get("sector") or {}
        priced = int(sector.get("priced", 0) or 0)
        advances = int((prices["change_pct"] > 0).sum()) if coverage and "change_pct" in prices.columns else 0
        declines = int((prices["change_pct"] < 0).sum()) if coverage and "change_pct" in prices.columns else 0
        unchanged = max(0, coverage - advances - declines)
        complete = coverage >= 475
        sector_complete = priced >= 475
        return {
            "complete": complete,
            "sector_complete": sector_complete,
            "evaluated": coverage,
            "sector_priced": priced,
            "nifty500_change_pct": snap.get("nifty_change"),
            "ad_ratio": snap.get("ad_ratio"),
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "positive_sectors": int(sector.get("positive_sectors", 0) or 0),
            "negative_sectors": int(sector.get("negative_sectors", 0) or 0),
            "quote_rows": prices,
            "reason": "" if complete and sector_complete else "CURRENT_ENGINE_COVERAGE_BELOW_95PCT",
        }
    except Exception as exc:
        import pandas as pd
        return {"complete": False, "sector_complete": False, "evaluated": 0, "sector_priced": 0,
                "nifty500_change_pct": None, "ad_ratio": None, "advances": 0, "declines": 0,
                "unchanged": 0, "positive_sectors": 0, "negative_sectors": 0,
                "reason": f"{type(exc).__name__}: {exc}", "quote_rows": pd.DataFrame()}

try:
    from market.nifty500_breadth import BREADTH as _breadth
    _breadth.snapshot = lambda force=False: _canonical_breadth_snapshot(force)
except Exception:
    pass

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
    # The original presentation layer used an obsolete 500/500 display gate.
    # Keep the design/text but show PASS whenever the canonical engine has the
    # approved >=95% (475/500) coverage.
    if "NIFTY 500 quotes" in text:
        match = re.search(r"NIFTY 500 quotes (\d+)/500", text)
        if match and int(match.group(1)) >= 475:
            text = text.replace("API: WAIT/ERROR", "API: PASS")
    return _original_markdown(text, *args, **kwargs)


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

# Real, recognized price-action strategy playbook. This is presentation-only:
# the engine continues to evaluate the canonical S1-S5 rules already implemented
# in strategy/nifty500_price_action_strategies.py.
st.markdown("""
<style>
.strategy-playbook{background:#0b1422;border:1px solid #294367;border-radius:12px;padding:12px;margin:14px 0}
.strategy-playbook-title{font-size:1.05rem;font-weight:900;color:#fff;margin-bottom:4px}
.strategy-playbook-sub{font-size:.72rem;color:#c8d2e1;margin-bottom:10px}
.strategy-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}
.strategy-box{background:#101b2b;border:1px solid #294367;border-radius:10px;padding:9px;min-height:132px}
.strategy-code{font-size:.68rem;font-weight:900;color:#7fa2d5}
.strategy-name{font-size:.78rem;font-weight:900;color:#fff;margin:3px 0 7px}
.strategy-line{font-size:.61rem;color:#dbe4ef;line-height:1.35;margin-top:4px}
.strategy-tag{display:inline-block;font-size:.55rem;font-weight:900;color:#9ed9b5;background:#10271d;border:1px solid #3e664e;border-radius:5px;padding:2px 5px;margin-top:6px}
@media(max-width:1000px){.strategy-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){.strategy-grid{grid-template-columns:repeat(1,1fr)}}
</style>
<div class="strategy-playbook">
  <div class="strategy-playbook-title">📚 REAL PRICE-ACTION STRATEGIES — S1–S5</div>
  <div class="strategy-playbook-sub">Recognized market setups mapped to the bot's existing canonical S1–S5 rules. No new signal logic is added here.</div>
  <div class="strategy-grid">
    <div class="strategy-box"><div class="strategy-code">S1 • LIQUIDITY SWEEP / RECLAIM</div><div class="strategy-name">PDH/PDL Sweep + Open Reclaim</div><div class="strategy-line"><b>Buy:</b> Open &gt; PDH → PDH touch/sweep → LTP reclaims open.</div><div class="strategy-line"><b>Sell:</b> Open &lt; PDL → PDL touch/sweep → LTP loses open.</div><div class="strategy-tag">SL: PDH / PDL • 1.25R</div></div>
    <div class="strategy-box"><div class="strategy-code">S2 • BREAKOUT + RETEST</div><div class="strategy-name">PDH/PDL Breakout Retest</div><div class="strategy-line"><b>Buy:</b> PDH breakout → retest PDH → reclaim.</div><div class="strategy-line"><b>Sell:</b> PDL breakdown → retest PDL → failure.</div><div class="strategy-tag">SL: Retest Low / High • 1.25R</div></div>
    <div class="strategy-box"><div class="strategy-code">S3 • FALSE BREAKOUT / REVERSAL</div><div class="strategy-name">Opposite PDH/PDL Sweep</div><div class="strategy-line"><b>Buy:</b> Open inside range → sweep PDL → reversal above open.</div><div class="strategy-line"><b>Sell:</b> Open inside range → sweep PDH → reversal below open.</div><div class="strategy-tag">SL: Today's Low / High • 1.25R</div></div>
    <div class="strategy-box"><div class="strategy-code">S4 • INTRADAY BREAKOUT</div><div class="strategy-name">Previous Intraday High/Low Break</div><div class="strategy-line"><b>Buy:</b> LTP breaks the previously formed intraday high.</div><div class="strategy-line"><b>Sell:</b> LTP breaks the previously formed intraday low.</div><div class="strategy-tag">SL: Prior Low / High • 1.25R</div></div>
    <div class="strategy-box"><div class="strategy-code">S5 • PDH/PDL BREAKOUT</div><div class="strategy-name">Direct Previous-Day Break</div><div class="strategy-line"><b>Buy:</b> Live LTP &gt; PDH.</div><div class="strategy-line"><b>Sell:</b> Live LTP &lt; PDL.</div><div class="strategy-tag">SL: PDH / PDL • 1.25R</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Exact page order from here: Journal (inside the original dashboard) ->
# Strategy Playbook -> Trade Path -> Test Trade -> Master Download -> Daily Trading Tip.
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
