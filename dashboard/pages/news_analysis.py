"""News Analysis: persistent Yahoo Finance headline decisions for paper-trading and backtesting."""
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from master_data import build_master_data

st.set_page_config(page_title="NSE Catalyst | News Analysis", page_icon="📰", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)

try:
    ensure_bot_running()
except Exception:
    pass
try:
    build_master_data()
except Exception as error:
    st.warning(f"Master data refresh warning: {type(error).__name__}: {error}")

NEWS = ROOT / "outputs" / "MASTER_NEWS_ANALYSIS.csv"
SIGNALS = ROOT / "outputs" / "signals.csv"

def read_frame(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

df = read_frame(NEWS)
if df.empty:
    df = read_frame(SIGNALS)

st.title("📰 News Analysis")
st.caption("Yahoo Finance headlines • deterministic sentiment • final BUY/SELL confirmation • retained for six-month research")

if df.empty:
    st.info("No news decisions have been recorded yet. They will appear when qualified candidates reach the news gate during market hours.")
    render_daily_footer()
    st.stop()

for col in ["news_confidence", "atr_pct", "rvol", "beta", "traded_value", "priority_rank", "nifty500_change_pct", "entry", "quantity", "actual_risk"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

if "timestamp" in df.columns:
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["TradeDate"] = df["timestamp_dt"].dt.strftime("%Y-%m-%d")
else:
    df["TradeDate"] = ""

if "approved" in df.columns:
    df["ApprovedBool"] = df["approved"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
else:
    df["ApprovedBool"] = False

sentiment = df.get("news_sentiment", pd.Series("NEUTRAL", index=df.index)).astype(str).str.upper()

c1, c2, c3, c4 = st.columns(4)
c1.metric("News Decisions", len(df))
c2.metric("🟢 Positive", int((sentiment == "POSITIVE").sum()))
c3.metric("🔴 Negative", int((sentiment == "NEGATIVE").sum()))
c4.metric("⚪ Neutral", int((sentiment == "NEUTRAL").sum()))

st.subheader("Today's News Gate")
today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
today_df = df[df["TradeDate"].eq(today)].copy()
if today_df.empty:
    st.info("No news decisions recorded today.")
else:
    cols = [c for c in ["timestamp", "symbol", "signal", "news_headline", "news_sentiment", "news_confidence", "news_reason", "ApprovedBool", "reason"] if c in today_df.columns]
    st.dataframe(today_df[cols].sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True, height=430)

st.subheader("Research / Backtest Record")
st.caption("Every recorded candidate decision remains in MASTER_NEWS_ANALYSIS.csv. Filter this record later to evaluate whether the news gate improved the strategy.")

f1, f2, f3 = st.columns(3)
with f1:
    dates = sorted(df["TradeDate"].dropna().unique().tolist(), reverse=True)
    selected_dates = st.multiselect("Trade date", dates, default=dates[:1] if dates else [])
with f2:
    selected_sentiment = st.multiselect("Sentiment", ["POSITIVE", "NEGATIVE", "NEUTRAL"], default=["POSITIVE", "NEGATIVE", "NEUTRAL"])
with f3:
    sides = sorted(df["signal"].dropna().astype(str).str.upper().unique().tolist()) if "signal" in df.columns else []
    selected_side = st.multiselect("Side", sides, default=sides)

filtered = df.copy()
if selected_dates:
    filtered = filtered[filtered["TradeDate"].isin(selected_dates)]
if selected_sentiment:
    filtered = filtered[sentiment.loc[filtered.index].isin(selected_sentiment)]
if selected_side and "signal" in filtered.columns:
    filtered = filtered[filtered["signal"].astype(str).str.upper().isin(selected_side)]

approved = filtered[filtered["ApprovedBool"]]
fc1, fc2, fc3 = st.columns(3)
fc1.metric("Filtered Decisions", len(filtered))
fc2.metric("Passed News Gate", len(approved))
fc3.metric("Rejected / Not Approved", max(0, len(filtered) - len(approved)))

cols = [c for c in ["TradeDate", "timestamp", "symbol", "signal", "news_headline", "news_sentiment", "news_confidence", "news_reason", "ApprovedBool", "candidate_id", "entry", "atr_pct", "rvol", "beta", "traded_value", "priority_rank", "reason"] if c in filtered.columns]
st.dataframe(filtered[cols].sort_values(["TradeDate", "timestamp"], ascending=False), use_container_width=True, hide_index=True, height=500)

st.download_button("⬇️ DOWNLOAD NEWS MASTER CSV", data=filtered.to_csv(index=False).encode("utf-8"), file_name="nse_catalyst_news_analysis.csv", mime="text/csv", width="stretch")
st.info("Backtest rule: use the recorded news decision at the candidate timestamp. Do not use later headlines when evaluating an earlier trade; this preserves the information available at the time of the decision.")
render_daily_footer()
