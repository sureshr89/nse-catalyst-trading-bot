"""Live NIFTY 500 constituent sample for dashboard data verification."""
import pandas as pd
import streamlit as st


def render_nifty500_sample():
    @st.fragment(run_every="15s")
    def _render():
        st.markdown("<div class='sec'>🔎 NIFTY 500 — LIVE STOCK DATA CHECK (5 SAMPLE STOCKS)</div>", unsafe_allow_html=True)
        try:
            from market.nifty500_breadth import BREADTH
            market = BREADTH.snapshot(force=False)
            quotes = market.get("quote_rows")
            if not market.get("complete") or not isinstance(quotes, pd.DataFrame) or len(quotes) != 500:
                st.warning("Waiting for a verified 500/500 Dhan snapshot. No partial stock data is shown.")
                return
            cols = [c for c in ["Symbol", "SecurityId", "LTP", "PreviousClose", "NetChange", "change_pct"] if c in quotes.columns]
            sample = quotes[cols].copy().sort_values("Symbol").head(5)
            sample["Change ₹"] = pd.to_numeric(sample.get("NetChange"), errors="coerce")
            if "Change ₹" in sample.columns and sample["Change ₹"].isna().all():
                sample["Change ₹"] = pd.to_numeric(sample["LTP"], errors="coerce") - pd.to_numeric(sample["PreviousClose"], errors="coerce")
            sample["Status"] = sample["change_pct"].apply(lambda x: "🟢 POSITIVE" if float(x) > 0 else "🔴 NEGATIVE" if float(x) < 0 else "⚪ UNCHANGED")
            sample = sample.rename(columns={"Symbol":"Stock", "LTP":"LTP ₹", "PreviousClose":"Prev Close ₹", "change_pct":"Change %"})
            show = sample[["Stock", "LTP ₹", "Prev Close ₹", "Change ₹", "Change %", "Status"]].copy()
            for c in ["LTP ₹", "Prev Close ₹", "Change ₹"]:
                show[c] = pd.to_numeric(show[c], errors="coerce").map(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "—")
            show["Change %"] = pd.to_numeric(show["Change %"], errors="coerce").map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
            st.dataframe(show, hide_index=True, width="stretch")
            st.caption("These are 5 actual constituents from the same verified 500/500 Dhan snapshot used for A/D and sector calculations. The sample is diagnostic only; all 500 stocks are used in the calculations.")
        except Exception as exc:
            st.error(f"NIFTY 500 sample check unavailable: {exc}")
    _render()
