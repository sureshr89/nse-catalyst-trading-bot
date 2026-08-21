"""Live NIFTY 500 Dhan diagnostic tab. No trades are created here."""
import pandas as pd
import streamlit as st

def _fmt(v, digits=2):
    try:return f"{float(v):,.{digits}f}"
    except Exception:return "—"

def _card(label,value):
    return f'<div class="diag-card"><div class="diag-label">{label}</div><div class="diag-value">{value}</div></div>'

@st.fragment(run_every="15s")
def _live_diagnostic():
    from market.nifty500_breadth import BREADTH
    from market.dhan_data import configured, dhan_status, diagnostic_nifty500_live, index_quote
    try:
        universe=BREADTH._get_universe()
        symbols=universe["Symbol"].astype(str).str.upper().str.strip().tolist() if not universe.empty else []
        mapping=BREADTH._get_mapping(symbols) if symbols else pd.DataFrame()
        diag=diagnostic_nifty500_live(mapping)
        idx=index_quote("NIFTY 500")
        rows=diag.get("rows") if isinstance(diag.get("rows"),pd.DataFrame) else pd.DataFrame()
        status=diag.get("status") or dhan_status()
        configured_ok=bool(diag.get("configured") and configured())
        requested=int(diag.get("requested",0) or 0);returned=int(diag.get("returned",0) or 0);valid=int(diag.get("valid",0) or 0)
        mapping_count=len(mapping)
        html="<div class='diag-grid'>"
        html+=_card("DHAN", "CONNECTED" if configured_ok else "NOT CONFIGURED")
        html+=_card("UNIVERSE", f"{len(symbols)}/500")
        html+=_card("SECURITY MAPPING", f"{mapping_count}/500")
        html+=_card("QUOTE REQUEST", f"{requested}/500")
        html+=_card("Dhan RETURNED", str(returned))
        html+=_card("VALID LIVE QUOTES", f"{valid}/500")
        html+=_card("95% GATE", "PASS" if valid>=475 else "BLOCK")
        html+=_card("NIFTY 500 LTP", f"₹{_fmt(idx.get('LTP'))}" if idx else "NO LIVE INDEX")
        html+="</div>"
        st.markdown(html,unsafe_allow_html=True)
        if valid:
            st.success(f"LIVE Dhan stock data received: {valid}/500. This tab shows raw live availability; it does not create trades.")
        else:
            st.error(f"NO LIVE STOCK QUOTES RECEIVED. Stage: {status.get('stage','—')} • {status.get('message','No Dhan quote response')}")
        st.write(f"**Last diagnostic:** {status.get('updated_at','—')} • HTTP {status.get('http_status','—')} • error {status.get('error_code','—')}")
        if idx:
            st.write(f"**NIFTY 500:** LTP ₹{_fmt(idx.get('LTP'))} • Previous close ₹{_fmt(idx.get('PreviousClose'))} • Change {float(idx.get('change_pct') or 0):+.2f}%")
        else:
            st.warning("NIFTY 500 index quote is also unavailable. This points to the Dhan/index mapping path, not S1-S5 strategy logic.")
        if not mapping.empty:
            st.markdown("#### Security mapping sample")
            st.dataframe(mapping[[c for c in ["Symbol","SecurityId","ExchangeSegment","Instrument"] if c in mapping.columns]].head(20),use_container_width=True,hide_index=True)
        if not rows.empty:
            st.markdown("#### Live Dhan stock values")
            show=[c for c in ["Symbol","SecurityId","LTP","TodayOpen","TodayHigh","TodayLow","PreviousClose","NetChange","change_pct","UpdatedAt"] if c in rows.columns]
            st.dataframe(rows[show].sort_values("Symbol").head(50),use_container_width=True,hide_index=True)
            missing=sorted(set(mapping.Symbol.astype(str).str.upper())-set(rows.Symbol.astype(str).str.upper())) if not mapping.empty else []
            if missing:
                st.markdown(f"#### Missing from Dhan response: {len(missing)}")
                st.dataframe(pd.DataFrame({"MissingSymbol":missing[:100]}),use_container_width=True,hide_index=True)
    except Exception as exc:
        st.error(f"LIVE TESTING ERROR: {type(exc).__name__}: {exc}")


def render_test_tab():
    st.subheader("🧪 LIVE NIFTY 500 DATA TEST")
    st.caption("Dhan live-data diagnostic only • refreshes every 15 seconds • no trade is created and no journal is modified.")
    _live_diagnostic()
    st.markdown("""
    <style>
    .diag-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:8px 0 12px}
    .diag-card{background:#101b2b;border:1px solid #294367;border-radius:9px;padding:9px 10px;min-height:58px}
    .diag-label{font-size:.55rem;color:#fff;margin-bottom:5px;font-weight:850;text-transform:uppercase}
    .diag-value{font-size:.9rem;color:#fff;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    @media(max-width:1000px){.diag-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>
    """,unsafe_allow_html=True)
