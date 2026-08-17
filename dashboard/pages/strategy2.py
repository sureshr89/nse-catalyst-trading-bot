from pathlib import Path
import sys
import json
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from strategy2_worker import ensure_strategy2_running, get_strategy2_status

st.set_page_config(page_title="NSE Catalyst | Strategy 2", page_icon=str(ROOT / "favicon.png"), layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="strategy2_live")
ensure_strategy2_running()
render_nav()

st.title("🔴 Strategy 2 — Gap-Up Extension Reversal SELL")
st.caption("Separate ₹2,50,000 paper capital • Highest opening GAP priority • No ATR")
status = get_strategy2_status()

cards = st.columns(4)
cards[0].metric("Status", status.get("status", "STARTING"))
cards[1].metric("Capital", f"₹{float(status.get('available_capital', 250000) or 0):,.0f}")
cards[2].metric("Open Positions", int(status.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", f"₹{float(status.get('daily_pnl', 0) or 0):,.0f}")
if status.get("message"):
    st.info(str(status["message"]))

st.markdown("### Exact Strategy")
st.markdown("**Today's Open > PDH → stock moves up → after 09:45 → first completed 1-minute CLOSE below Today's Open → SELL → SL Today's High → Target PDH.**")
st.caption("Priority is the largest opening GAP % from Previous Day Close. NIFTY/news are practical protective filters, not rigid multi-indicator gates.")

tab_current, tab_analysis, tab_scanner, tab_news, tab_downloads = st.tabs(["📌 Current Trading", "📊 Analysis", "🔎 Stock Scanner", "📰 News", "⬇️ Downloads"])

with tab_current:
    diagnostics = status.get("diagnostics", {}) or {}
    st.subheader("Live Strategy 2 State")
    st.write({"last_scan": status.get("last_scan"), "last_signal_count": status.get("last_signal_count", 0), "candidates": diagnostics.get("candidates", 0), "qualified": diagnostics.get("qualified", 0), "signals": diagnostics.get("signals", 0)})
    rejections = diagnostics.get("rejections", {}) or {}
    if rejections:
        st.subheader("Rejections")
        st.dataframe(pd.DataFrame([{"Reason": k, "Count": v} for k, v in rejections.items()]), use_container_width=True, hide_index=True)

with tab_analysis:
    path = ROOT / "outputs" / "strategy2_diagnostics.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        st.subheader("Strategy 2 Analysis")
        st.json(data)
    else:
        st.info("Strategy 2 analysis will appear after the first scan.")

with tab_scanner:
    path = ROOT / "outputs" / "gap_analysis.csv"
    if path.exists():
        df = pd.read_csv(path)
        if "GapPercentFromPreviousClose" in df.columns:
            df = df.sort_values("GapPercentFromPreviousClose", key=lambda s: s.abs(), ascending=False)
        st.subheader("Opening GAP Priority Board")
        st.dataframe(df.head(100), use_container_width=True, hide_index=True)
    else:
        st.info("Gap analysis will appear after market-data preparation.")

with tab_news:
    path = ROOT / "outputs" / "strategy2_signals.csv"
    if path.exists():
        df = pd.read_csv(path)
        cols = [c for c in ["timestamp", "symbol", "gap_percent", "news_sentiment", "news_confidence", "news_headline", "approved", "reason"] if c in df.columns]
        st.dataframe(df[cols].tail(100), use_container_width=True, hide_index=True)
    else:
        st.info("Strategy 2 news decisions will appear after signals are evaluated.")

with tab_downloads:
    for filename, label in [("strategy2_trades.csv", "Strategy 2 Trades"), ("strategy2_signals.csv", "Strategy 2 Signals")]:
        path = ROOT / "outputs" / filename
        if path.exists():
            st.download_button(f"Download {label}", path.read_bytes(), file_name=filename, mime="text/csv")
        else:
            st.caption(f"{label}: no data yet.")
