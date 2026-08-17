from pathlib import Path
import sys
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import status, diagnostics, state, signals, gaps, format_price, format_pct, today_signals, approved_today

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Current", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="s2_current_live")
ensure_strategy2_running()
render_nav()

s = get_strategy2_status() or status()
d = diagnostics()
st.title("🔴 Strategy 2 — Current Trading")
st.caption("Gap-Up Extension Reversal SELL • separate ₹2,50,000 paper account • completed 1-minute data")

cards = st.columns(5)
cards[0].metric("Status", s.get("status", "STARTING"))
cards[1].metric("Available Capital", format_price(s.get("available_capital", 250000)))
cards[2].metric("Open Positions", int(s.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", format_price(s.get("daily_pnl", 0)))
cards[4].metric("Qualified", int((d or {}).get("qualified", 0) or 0))
if s.get("message"):
    st.info(str(s["message"]))

st.subheader("⚡ Exact Entry Rules")
st.dataframe(pd.DataFrame([
    ("Setup", "Today's Open > PDH"),
    ("Extension", "After 09:45, price must trade above Today's Open"),
    ("Trigger", "First completed 1-minute CLOSE below Today's Open"),
    ("Side", "SELL only"),
    ("Stop", "Today's High at the trigger"),
    ("Target", "PDH"),
    ("Priority", "Largest opening GAP % from Previous Day Close first"),
    ("NIFTY", "Only clearly bullish NIFTY 500 (> +0.25%) blocks the short"),
    ("Risk", "Same ₹1,400–₹1,500 intended risk / 1.25R gate as Strategy 1"),
], columns=["Condition", "Rule"]), use_container_width=True, hide_index=True)

st.subheader("📡 Live Scan State")
last_scan = s.get("last_scan") or "Not scanned yet"
st.write({
    "last_scan": last_scan,
    "signals_in_last_scan": int(s.get("last_signal_count", 0) or 0),
    "opening_gap_candidates": int(d.get("candidates", 0) or 0),
    "qualified_reversals": int(d.get("qualified", 0) or 0),
    "approved_signals": int(d.get("signals", 0) or 0),
    "rejections": d.get("rejections", {}) or {},
})

st.subheader("🎯 Today's Qualified / Approved Signals")
q = today_signals()
if not q.empty:
    cols = [c for c in ["timestamp", "symbol", "gap_percent", "today_open", "pdh", "trigger_close", "entry", "stop_loss", "target", "risk_reward", "priority_rank", "news_sentiment", "approved", "reason"] if c in q.columns]
    st.dataframe(q[cols].tail(50).iloc[::-1], use_container_width=True, hide_index=True, height=330)
else:
    st.info("No Strategy 2 signal decisions recorded today.")

st.subheader("📍 Open Positions")
positions = (state().get("open_positions", {}) or {})
if positions:
    rows = []
    for symbol, p in positions.items():
        rows.append({"Stock": symbol, "Side": p.get("signal"), "Entry": format_price(p.get("entry")), "SL": format_price(p.get("stop_loss")), "Target": format_price(p.get("target")), "Qty": p.get("quantity"), "Gap %": format_pct(p.get("gap_percent")), "Entry Time": p.get("entry_time", "—")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No open Strategy 2 paper positions.")

st.subheader("🚫 Rejection Audit")
rejections = d.get("rejections", {}) or {}
if rejections:
    st.dataframe(pd.DataFrame([{"Reason": k, "Count": v} for k, v in sorted(rejections.items(), key=lambda x: x[1], reverse=True)]), use_container_width=True, hide_index=True)
else:
    st.info("No rejections recorded in the latest scan cycle.")

st.caption("Auto-refresh 5s • scan cycle 30s • paper trading only • live orders disabled")
render_daily_footer()
