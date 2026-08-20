"""Read-only dashboard test panel.

This module never writes files, creates signals/trades, or calculates
win/loss/P&L. It only displays a live diagnostic snapshot.
"""
import pandas as pd
import streamlit as st


def render_test_tab():
    st.markdown("### 🧪 TEST — Data & Entry Check")
    st.caption(
        "READ-ONLY TEST ONLY • No S1–S5 changes • No signals.csv/trades.csv writes "
        "• No win/loss/P&L calculation"
    )

    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured, index_quote

        snap = BREADTH.snapshot(force=False)
        q = snap.get("quote_rows")
        rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
        complete = bool(snap.get("complete")) and len(rows) == 500
        sector_ok = bool(snap.get("sector_complete")) and int(
            snap.get("sector_priced", 0) or 0
        ) == 500
        idx = index_quote("NIFTY 500")

        checks = [
            ("Dhan connected", configured()),
            ("500/500 stock quotes", complete),
            ("500/500 sector data", sector_ok),
            ("NIFTY 500 index", bool(idx)),
            ("A/D available", snap.get("ad_ratio") is not None),
        ]
        cols = st.columns(len(checks))
        for col, (label, ok) in zip(cols, checks):
            col.metric(label, "PASS" if ok else "WAIT")

        st.markdown("#### Live data check")
        st.write(
            {
                "NIFTY 500 LTP": idx.get("LTP") if idx else None,
                "Previous Close": idx.get("PreviousClose") if idx else None,
                "Net Change": idx.get("NetChange") if idx else None,
                "Advances": snap.get("advances", 0),
                "Declines": snap.get("declines", 0),
                "Unchanged": snap.get("unchanged", 0),
                "A/D Ratio": snap.get("ad_ratio"),
                "Positive Sectors": snap.get("positive_sectors", 0),
                "Negative Sectors": snap.get("negative_sectors", 0),
            }
        )

        if not rows.empty:
            view = rows.copy()
            if "LTP" in view.columns and "PreviousClose" in view.columns:
                view["ChangePct"] = (
                    (view["LTP"] - view["PreviousClose"])
                    / view["PreviousClose"].replace(0, pd.NA)
                    * 100
                )
            if "LTP" in view.columns and "TodayOpen" in view.columns:
                view["SideCheck"] = view.apply(
                    lambda r: "BUY"
                    if r["LTP"] > r["TodayOpen"]
                    else "SELL"
                    if r["LTP"] < r["TodayOpen"]
                    else "FLAT",
                    axis=1,
                )
            wanted = [
                "Symbol",
                "LTP",
                "TodayOpen",
                "PreviousClose",
                "NetChange",
                "ChangePct",
                "SideCheck",
            ]
            sample = view[[c for c in wanted if c in view.columns]].head(5)
            st.markdown("#### Sample price-vs-open check")
            st.dataframe(sample, use_container_width=True, hide_index=True)

        st.info(
            "TEST ONLY: BUY/SELL above is only a diagnostic price-vs-open check. "
            "It is NOT a strategy signal, NOT stored anywhere, NOT sent to the "
            "paper executor, and NOT included in any win/loss calculation."
        )
    except Exception as exc:
        st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
