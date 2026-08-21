"""Live NIFTY 500 Dhan diagnostic tab. No trades are created here."""
import math
import pandas as pd
import streamlit as st


def _fmt(v, digits=2):
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "—"


def _card(label, value):
    return f'<div class="diag-card"><div class="diag-label">{label}</div><div class="diag-value">{value}</div></div>'


def _parse_live_rows(response, mapping):
    """Parse the Dhan response locally so this tab does not depend on a new
    helper being present in a cached Streamlit module."""
    data = response.get("data", {}).get("NSE_EQ", {}) if response else {}
    by_id = dict(zip(mapping["SecurityId"].astype(str), mapping["Symbol"].astype(str).str.upper()))
    rows = []
    for sid, item in data.items():
        if str(sid) not in by_id or not isinstance(item, dict):
            continue
        ohlc = item.get("ohlc") or {}
        try:
            ltp = float(item.get("last_price") or 0)
            op = float(ohlc.get("open") or 0)
            hi = float(ohlc.get("high") or 0)
            lo = float(ohlc.get("low") or 0)
            prev = float(ohlc.get("close") or 0)
            net = float(item.get("net_change")) if item.get("net_change") is not None else ltp - prev
            vol = float(item.get("volume") or 0)
            valid = (
                all(math.isfinite(x) and x > 0 for x in (ltp, op, hi, lo, prev))
                and hi >= max(op, lo, ltp)
                and lo <= min(op, hi, ltp)
                and math.isfinite(net)
                and vol >= 0
            )
            if not valid:
                continue
            rows.append({
                "Symbol": by_id[str(sid)],
                "SecurityId": str(sid),
                "LTP": ltp,
                "TodayOpen": op,
                "TodayHigh": hi,
                "TodayLow": lo,
                "PreviousClose": prev,
                "NetChange": net,
                "change_pct": (ltp - prev) / prev * 100.0,
                "Volume": vol,
            })
        except (TypeError, ValueError, OverflowError):
            continue
    return pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame()


@st.fragment(run_every="15s")
def _live_diagnostic():
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured, dhan_status, _marketfeed, index_quote

        universe = BREADTH._get_universe()
        symbols = universe["Symbol"].astype(str).str.upper().str.strip().tolist() if not universe.empty else []
        mapping = BREADTH._get_mapping(symbols) if symbols else pd.DataFrame()
        configured_ok = bool(configured())

        response = {}
        if configured_ok and not mapping.empty:
            ids = mapping["SecurityId"].astype(str).tolist()
            response = _marketfeed("NSE_EQ", ids, "/marketfeed/quote")
        rows = _parse_live_rows(response, mapping) if not mapping.empty else pd.DataFrame()
        raw = response.get("data", {}).get("NSE_EQ", {}) if response else {}
        returned = len(raw) if isinstance(raw, dict) else 0
        valid = len(rows)
        idx = index_quote("NIFTY 500") if configured_ok else None
        status = dhan_status()

        html = "<div class='diag-grid'>"
        html += _card("DHAN", "CONNECTED" if configured_ok else "NOT CONFIGURED")
        html += _card("UNIVERSE", f"{len(symbols)}/500")
        html += _card("SECURITY MAPPING", f"{len(mapping)}/500")
        html += _card("QUOTE REQUEST", f"{len(mapping)}/500")
        html += _card("DHAN RETURNED", str(returned))
        html += _card("VALID LIVE QUOTES", f"{valid}/500")
        html += _card("95% GATE", "PASS" if valid >= 475 else "BLOCK")
        html += _card("NIFTY 500 LTP", f"₹{_fmt(idx.get('LTP'))}" if idx else "NO LIVE INDEX")
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        if valid:
            st.success(f"LIVE Dhan stock data received: {valid}/500. This diagnostic does not create trades.")
        elif returned:
            st.warning(f"Dhan returned {returned} quote records, but none passed local OHLC validation. This is a DATA/PARSING issue, not an S1-S5 issue.")
        else:
            st.error(f"NO LIVE STOCK QUOTES RECEIVED. Stage: {status.get('stage', '—')} • {status.get('message', 'No Dhan quote response')}")

        st.write(
            f"**Dhan diagnostic:** {status.get('updated_at', '—')} • "
            f"HTTP {status.get('http_status', '—')} • error {status.get('error_code', '—')}"
        )

        if idx:
            st.write(
                f"**NIFTY 500:** LTP ₹{_fmt(idx.get('LTP'))} • "
                f"Previous close ₹{_fmt(idx.get('PreviousClose'))} • "
                f"Change {float(idx.get('change_pct') or 0):+.2f}%"
            )
        else:
            st.warning("NIFTY 500 index quote is unavailable. Check the Dhan index mapping/API path.")

        if not mapping.empty:
            st.markdown("#### Security mapping sample")
            cols = [c for c in ["Symbol", "SecurityId", "ExchangeSegment", "Instrument"] if c in mapping.columns]
            st.dataframe(mapping[cols].head(20), use_container_width=True, hide_index=True)

        if not rows.empty:
            st.markdown("#### LIVE Dhan stock values")
            show = [c for c in ["Symbol", "SecurityId", "LTP", "TodayOpen", "TodayHigh", "TodayLow", "PreviousClose", "NetChange", "change_pct", "Volume"] if c in rows.columns]
            st.dataframe(rows[show].sort_values("Symbol").head(100), use_container_width=True, hide_index=True)
            missing = sorted(set(mapping.Symbol.astype(str).str.upper()) - set(rows.Symbol.astype(str).str.upper()))
            if missing:
                st.markdown(f"#### Missing from Dhan response: {len(missing)}")
                st.dataframe(pd.DataFrame({"MissingSymbol": missing[:100]}), use_container_width=True, hide_index=True)
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
    """, unsafe_allow_html=True)
