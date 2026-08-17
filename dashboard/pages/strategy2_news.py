from pathlib import Path
import sys
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.strategy2_data import signals, today_signals

st.set_page_config(page_title="NSE Catalyst | Strategy 2 News", page_icon="📰", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

st.title("📰 Strategy 2 — News Analysis")
st.caption("News is evaluated only at the Strategy 2 candidate decision point; every decision is journaled separately.")

df = today_signals()
if df.empty:
    st.info("No Strategy 2 news decisions recorded today.")
else:
    sentiment = df.get("news_sentiment", pd.Series(dtype=str)).astype(str).str.upper()
    a, b, c, d = st.columns(4)
    a.metric("Decisions", len(df))
    b.metric("🟢 Positive", int(sentiment.eq("POSITIVE").sum()))
    c.metric("🔴 Negative", int(sentiment.eq("NEGATIVE").sum()))
    d.metric("⚪ Neutral", int(sentiment.eq("NEUTRAL").sum()))
    st.subheader("Decision Audit")
    cols = [c for c in ["timestamp", "symbol", "gap_percent", "news_sentiment", "news_confidence", "news_headline", "news_reason", "news_source", "approved", "reason"] if c in df.columns]
    st.dataframe(df[cols].tail(200).iloc[::-1], use_container_width=True, hide_index=True, height=500)

st.subheader("📚 All Strategy 2 News Records")
all_df = signals()
if not all_df.empty:
    cols = [c for c in ["timestamp", "symbol", "news_sentiment", "news_confidence", "news_headline", "approved", "reason"] if c in all_df.columns]
    st.dataframe(all_df[cols].tail(500).iloc[::-1], use_container_width=True, hide_index=True, height=420)
else:
    st.info("No historical Strategy 2 signal records yet.")

st.caption("Strategy 2 uses the same news decision framework as Strategy 1 but writes to its own signal journal.")
render_daily_footer()
