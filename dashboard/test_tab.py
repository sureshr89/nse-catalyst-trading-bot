"""Dashboard-only TEST panel. Read-only; never creates signals, trades, or journal rows."""
import streamlit as st
import pandas as pd


def _fmt(v, digits=2):
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "—"


def render_test_tab():
    """Render the standalone TEST panel only; no trading/storage side effects."""
    st.markdown("## 🧪 TEST — Live Data / Entry Check")
    st.caption("READ-ONLY • live verification only • no signals • no trades • no journal • no P&L/W-L • S1–S5 unchanged")

    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured, index_quote

        snap = BREADTH.snapshot(force=False)
        q = snap.get("quote_rows")
        rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
        complete = bool(snap.get("complete")) and len(rows) == 500
        sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
        idx = index_quote("NIFTY 500")

        st.markdown("### 1. Data integrity")
        checks = [
            ("Dhan", configured()),
            ("Stocks", complete),
            ("Sectors", sector_ok),
            ("NIFTY 500", bool(idx)),
            ("A/D", snap.get("ad_ratio") is not None),
        ]
        cols = st.columns(5)
        for col, (label, ok) in zip(cols, checks):
            with col:
                st.markdown(
                    f'<div class="test-card"><div class="test-label">{label}</div>'
                    f'<div class="test-status {"pass" if ok else "wait"}">{"PASS" if ok else "WAIT"}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("### 2. NIFTY 500 live index")
        if idx:
            ltp = float(idx.get("LTP") or 0)
            prev = float(idx.get("PreviousClose") or 0)
            net = float(idx.get("NetChange") or (ltp - prev))
            pct = (net / prev * 100) if prev else 0.0
            a, b, c, d = st.columns(4)
            a.metric("LTP", f"₹{ltp:,.2f}")
            b.metric("Previous Close", f"₹{prev:,.2f}")
            c.metric("Change", f"{net:+,.2f}")
            d.metric("Change %", f"{pct:+.2f}%")
        else:
            st.warning("NIFTY 500 quote not available in this cycle.")

        st.markdown("### 3. Breadth & sectors")
        a, b, c, d, e = st.columns(5)
        a.metric("Advances", int(snap.get("advances", 0) or 0))
        b.metric("Declines", int(snap.get("declines", 0) or 0))
        c.metric("Unchanged", int(snap.get("unchanged", 0) or 0))
        c2 = snap.get("ad_ratio")
        d.metric("A / D", _fmt(c2, 2) if c2 is not None else "—")
        e.metric("Sectors + / −", f"{int(snap.get('positive_sectors', 0) or 0)} / {int(snap.get('negative_sectors', 0) or 0)}")

        st.markdown("### 4. Five-stock live sample")
        if not rows.empty:
            work = rows.copy()
            for col in ["LTP", "TodayOpen", "PreviousClose", "NetChange"]:
                if col in work.columns:
                    work[col] = pd.to_numeric(work[col], errors="coerce")
            if "NetChange" in work.columns and "PreviousClose" in work.columns:
                work["ChangePct"] = (work["NetChange"] / work["PreviousClose"] * 100).round(2)
            else:
                work["ChangePct"] = ((work["LTP"] - work["PreviousClose"]) / work["PreviousClose"] * 100).round(2)
            work["SideCheck"] = work.apply(
                lambda r: "BUY" if r["LTP"] > r["TodayOpen"]
                else "SELL" if r["LTP"] < r["TodayOpen"] else "FLAT", axis=1
            )
            display = work.head(5).copy()
            display = display.rename(columns={
                "Symbol": "Stock", "LTP": "LTP ₹", "TodayOpen": "Open ₹",
                "ChangePct": "Change %", "SideCheck": "Price vs Open",
            })
            keep = [c for c in ["Stock", "LTP ₹", "Open ₹", "Change %", "Price vs Open"] if c in display.columns]
            display = display[keep]
            st.dataframe(display, use_container_width=True, hide_index=True)
            st.caption("The five rows above come from the same verified NIFTY 500 snapshot used by the dashboard. Price-vs-open is only a diagnostic; it does not create a signal or trade.")
        else:
            st.warning("Waiting for the verified 500-stock snapshot.")

        st.markdown("### TEST isolation")
        st.info("This panel is read-only. It does not write signals.csv, trades.csv, journal data, win/loss, P&L, or S1–S5 state.")

        st.markdown("""
        <style>
        .test-card{background:#0b1726;border:1px solid #294b70;border-radius:10px;padding:10px 12px;min-height:72px;margin-bottom:8px}
        .test-label{font-size:12px;color:#9fb0c3;margin-bottom:7px;font-weight:600}
        .test-status{display:inline-block;font-size:14px;font-weight:700;padding:3px 10px;border-radius:14px}
        .test-status.pass{background:#063d22;color:#57e389}
        .test-status.wait{background:#3a2b05;color:#ffd45a}
        [data-testid="stDataFrame"]{font-size:13px}
        </style>
        """, unsafe_allow_html=True)

    except Exception as exc:
        st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
