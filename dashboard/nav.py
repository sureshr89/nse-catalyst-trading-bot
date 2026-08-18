import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


def _link(label, page):
    st.page_link(page, label=label)


def _row(left, right):
    cols = st.columns(2, gap="small")
    with cols[0]:
        if left[0]: _link(left[0], left[1])
    with cols[1]:
        if right[0]: _link(right[0], right[1])


@st.cache_data(ttl=10, show_spinner=False)
def _ad_ratio_snapshot():
    """Return a short-lived NIFTY 500 A/D snapshot using live 1m prices.

    This is a shared confirmation display for S1/S2. It does not change either
    strategy's entry logic. Previous close is taken from the same daily market
    data source rather than using the previous 1-minute candle.
    """
    try:
        from data.stock_universe import StockUniverse
        from market.price_data import PriceData
        universe = StockUniverse().get_dataframe(refresh=False)
        if universe.empty or "Symbol" not in universe.columns:
            return None
        symbols = universe["Symbol"].astype(str).str.upper().drop_duplicates().tolist()
        if not symbols:
            return None
        prices = PriceData()
        intraday = prices.get_multi_1m(symbols)
        daily = prices.get_multi_daily(symbols, period="5d")
        advances = declines = unchanged = available = 0
        for symbol in symbols:
            frame = intraday.get(symbol) if isinstance(intraday, dict) else None
            if frame is None or frame.empty or "Close" not in frame.columns:
                continue
            try:
                frame = frame.copy()
                if "Datetime" in frame.columns:
                    frame["Datetime"] = pd.to_datetime(frame["Datetime"], errors="coerce")
                    frame = frame.dropna(subset=["Datetime"]).sort_values("Datetime")
                current = float(frame.iloc[-1]["Close"])
                dframe = daily.get(symbol) if isinstance(daily, dict) else None
                if dframe is None or dframe.empty or "Close" not in dframe.columns:
                    continue
                dframe = dframe.copy()
                if "Datetime" in dframe.columns:
                    dframe["Datetime"] = pd.to_datetime(dframe["Datetime"], errors="coerce")
                    dframe = dframe.dropna(subset=["Datetime"]).sort_values("Datetime")
                if len(dframe) < 2:
                    continue
                previous = float(dframe.iloc[-2]["Close"])
                if previous <= 0:
                    continue
                available += 1
                if current > previous:
                    advances += 1
                elif current < previous:
                    declines += 1
                else:
                    unchanged += 1
            except (TypeError, ValueError, KeyError, IndexError):
                continue
        ratio = advances / declines if declines else (float(advances) if advances else 0.0)
        if ratio >= 1.50:
            bias = "STRONG BULLISH"
        elif ratio >= 1.00:
            bias = "BULLISH"
        elif ratio >= 0.67:
            bias = "BEARISH"
        else:
            bias = "STRONG BEARISH"
        return {"advances": advances, "declines": declines, "unchanged": unchanged, "available": available, "total": len(symbols), "ratio": ratio, "bias": bias, "updated": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")}
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


def _render_ad_panel():
    snapshot = _ad_ratio_snapshot()
    if not snapshot: return
    if snapshot.get("error"):
        st.caption(f"A/D Ratio unavailable: {snapshot['error']}")
        return
    st.markdown(
        f"""
        <div style='border:1px solid #303A4B;border-radius:12px;padding:10px 12px;margin:8px 0 12px;background:#111722'>
          <div style='display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap'>
            <div><b>📊 NIFTY 500 Advance / Decline</b><br><small>Live confirmation filter • refreshed every ~10 seconds • {snapshot['updated']} IST</small></div>
            <div><b>A/D Ratio: {snapshot['ratio']:.2f}</b> • {snapshot['bias']}</div>
          </div>
          <div style='margin-top:6px'><small>Advances: <b>{snapshot['advances']}</b> &nbsp; Declines: <b>{snapshot['declines']}</b> &nbsp; Unchanged: <b>{snapshot['unchanged']}</b> &nbsp; Coverage: <b>{snapshot['available']}/{snapshot['total']}</b></small></div>
          <div style='margin-top:5px'><small>&gt;1.50 strong bullish • 1.00–1.49 bullish • 0.67–0.99 bearish • &lt;0.67 strong bearish. Confirmation only — S1/S2 entry logic is unchanged.</small></div>
        </div>
        """, unsafe_allow_html=True,
    )


def render_nav(top_offset=0):
    """Shared strategy selector and live NIFTY 500 A/D confirmation panel."""
    if top_offset:
        st.write(""); st.write("")
    st.markdown("""
    <style>
    .nse-nav-title{font-size:.72rem;font-weight:800;letter-spacing:.05em;margin:8px 0 6px;text-transform:uppercase}
    .nse-nav-title.main{color:#A9B7CA}
    [data-testid="stPageLink"]{width:100%!important;margin:0!important}
    [data-testid="stPageLink"] a{width:100%!important;min-height:50px!important;border:1px solid #303A4B!important;border-radius:12px!important;background:#151B26!important;padding:7px 5px!important;box-sizing:border-box!important;display:flex!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis}
    [data-testid="stPageLink"] a:hover{border-color:#59769F!important;background:#192233!important}
    [data-testid="stPageLink"] a p{overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important;margin:0!important}
    @media(max-width:700px){[data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;width:100%!important;gap:.5rem!important}[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{flex:1 1 0!important;width:calc(50% - .25rem)!important;min-width:0!important;max-width:none!important}[data-testid="stPageLink"] a{min-height:50px!important;padding:6px 4px!important;font-size:.74rem!important}}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="nse-nav-title main">🏠 STRATEGIES</div>', unsafe_allow_html=True)
    _row(("🔵 STRATEGY 1", "pages/current_trading.py"), ("🔴 STRATEGY 2", "pages/strategy2_current.py"))
    _render_ad_panel()
