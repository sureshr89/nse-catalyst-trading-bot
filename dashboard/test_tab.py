"""Dashboard-only test tab. It never creates signals, trades, or journal rows."""
import streamlit as st
import pandas as pd


def render_test_tab():
    tab = st.tabs(["🧪 TEST — Data & Entry Check"])[0]
    with tab:
        st.markdown("### 🧪 TEST — Data & Entry Check")
        st.caption("Read-only test. S1–S5, signals.csv and trades.csv are not modified.")
        try:
            from market.nifty500_breadth import BREADTH
            from market.dhan_data import configured, dhan_status, index_quote
            snap = BREADTH.snapshot(force=False)
            q = snap.get("quote_rows")
            rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
            complete = bool(snap.get("complete")) and len(rows) == 500
            sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
            idx = index_quote("NIFTY 500")
            checks = [
                ("Dhan connected", configured()),
                ("500/500 stock quotes", complete),
                ("500/500 sector data", sector_ok),
                ("NIFTY 500 index quote", bool(idx)),
                ("A/D available", snap.get("ad_ratio") is not None),
            ]
            c = st.columns(len(checks))
            for col, (label, ok) in zip(c, checks):
                col.metric(label, "PASS" if ok else "WAIT")
            if idx:
                st.write({"NIFTY 500 LTP": idx.get("LTP"), "Previous Close": idx.get("PreviousClose"), "Change": idx.get("NetChange")})
            st.write({"Advances": snap.get("advances", 0), "Declines": snap.get("declines", 0), "Unchanged": snap.get("unchanged", 0), "A/D": snap.get("ad_ratio"), "Positive sectors": snap.get("positive_sectors", 0), "Negative sectors": snap.get("negative_sectors", 0)})
            if not rows.empty:
                rows["ChangePct"] = (rows["LTP"] - rows["PreviousClose"]) / rows["PreviousClose"] * 100
                rows["SideCheck"] = rows.apply(lambda r: "BUY" if r["LTP"] > r["TodayOpen"] else "SELL" if r["LTP"] < r["TodayOpen"] else "FLAT", axis=1)
                sample = rows[[c for c in ["Symbol", "LTP", "TodayOpen", "PreviousClose", "NetChange", "ChangePct", "SideCheck"] if c in rows.columns]].head(5)
                st.dataframe(sample, use_container_width=True, hide_index=True)
                st.info("TEST ONLY: the BUY/SELL side shown here is a read-only price-vs-open check. It does not create or execute a trade.")
        except Exception as exc:
            st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
