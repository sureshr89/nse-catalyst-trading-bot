from pathlib import Path
import sys
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import status, diagnostics, state, format_price, format_pct, today_signals

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Current", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="s2_current_live")
ensure_strategy2_running()
render_nav()

s = get_strategy2_status() or status()
d = diagnostics() or {}
st.title("🔴 Strategy 2 — Current Trading")
st.caption("Gap Extension Reversal BUY + SELL • separate ₹2,50,000 paper account • completed 1-minute data")

cards = st.columns(6)
cards[0].metric("Status", str(s.get("status", "STARTING")))
cards[1].metric("Available Capital", format_price(s.get("available_capital", 250000)))
cards[2].metric("Open Positions", int(s.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", format_price(s.get("daily_pnl", 0)))
cards[4].metric("BUY Qualified", int(d.get("buy_qualified", 0) or 0))
cards[5].metric("SELL Qualified", int(d.get("sell_qualified", 0) or 0))
if s.get("message"): st.info(str(s["message"]))

st.subheader("⚡ Exact Strategy 2 Rules")
rules_df = pd.DataFrame([
    ("SELL setup", "Today's Open > PDH"),
    ("SELL extension", "After 09:45, price trades above Today's Open"),
    ("SELL trigger", "First completed 1-minute CLOSE below Today's Open"),
    ("SELL SL / Target", "Today's High at trigger / PDH"),
    ("BUY setup", "Today's Open < PDL"),
    ("BUY extension", "After 09:45, price trades below Today's Open"),
    ("BUY trigger", "First completed 1-minute CLOSE above Today's Open"),
    ("BUY SL / Target", "Today's Low at trigger / PDL"),
    ("Priority", "Largest absolute opening GAP % from Previous Day Close first"),
    ("NIFTY", "Soft protective filter: clearly bullish blocks SELL; clearly bearish blocks BUY"),
    ("Risk", "₹1,400–₹1,500 intended risk / minimum 1.25R"),
    ("Capital", "Separate ₹2,50,000 paper account"),
], columns=["Condition", "Rule"])
st.dataframe(rules_df.astype(str), width="stretch", hide_index=True)

st.subheader("📡 Live Scan State")
scan_rows = [
    ("Last scan", str(s.get("last_scan") or "Not scanned yet")),
    ("Signals in last scan", str(int(s.get("last_signal_count", 0) or 0))),
    ("Opening GAP candidates", str(int(d.get("candidates", 0) or 0))),
    ("BUY candidates", str(int(d.get("buy_candidates", 0) or 0))),
    ("SELL candidates", str(int(d.get("sell_candidates", 0) or 0))),
    ("BUY qualified", str(int(d.get("buy_qualified", 0) or 0))),
    ("SELL qualified", str(int(d.get("sell_qualified", 0) or 0))),
    ("Approved signals", str(int(d.get("signals", 0) or 0))),
]
st.dataframe(pd.DataFrame(scan_rows, columns=["Metric", "Value"]).astype(str), width="stretch", hide_index=True)

st.subheader("🎯 Today's Qualified / Approved Signals")
q = today_signals()
if not q.empty:
    cols = [c for c in ["timestamp", "symbol", "signal", "gap_percent", "today_open", "pdh", "pdl", "trigger_close", "entry", "stop_loss", "target", "risk_reward", "priority_rank", "news_sentiment", "approved", "reason"] if c in q.columns]
    st.dataframe(q[cols].tail(100).iloc[::-1], width="stretch", hide_index=True, height=360)
else:
    st.info("No Strategy 2 signal decisions recorded today.")

st.subheader("📍 Open Positions")
positions = (state().get("open_positions", {}) or {})
if positions:
    rows = []
    for symbol, p in positions.items():
        rows.append({"Stock": symbol, "Side": p.get("signal"), "Entry": format_price(p.get("entry")), "SL": format_price(p.get("stop_loss")), "Target": format_price(p.get("target")), "Qty": p.get("quantity"), "Gap %": format_pct(p.get("gap_percent")), "Entry Time": p.get("entry_time", "—")})
    st.dataframe(pd.DataFrame(rows).astype(str), width="stretch", hide_index=True)
else:
    st.info("No open Strategy 2 paper positions.")

st.subheader("🚫 Rejection Audit")
rejections = d.get("rejections", {}) or {}
if rejections:
    rejection_rows = [{"Reason": str(k), "Count": str(v)} for k, v in sorted(rejections.items(), key=lambda x: int(x[1] or 0), reverse=True)]
    st.dataframe(pd.DataFrame(rejection_rows).astype(str), width="stretch", hide_index=True)
else:
    st.info("No rejections recorded in the latest scan cycle.")

st.caption("Auto-refresh 5s • scan cycle 30s • paper trading only • live orders disabled")
render_daily_footer()
