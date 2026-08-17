from pathlib import Path
import sys
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from strategy2_worker import ensure_strategy2_running, get_strategy2_status
from dashboard.strategy2_data import diagnostics, format_price

st.set_page_config(page_title="NSE Catalyst | Strategy 2", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="s2_home_live")
ensure_strategy2_running()
render_nav()

s = get_strategy2_status() or {}
d = diagnostics() or {}
st.title("🔴 Strategy 2 — Gap Extension Reversal")
st.caption("Independent ₹2,50,000 paper strategy • BUY + SELL • same dashboard standard as Strategy 1")

cards = st.columns(6)
cards[0].metric("Worker", s.get("status", "STARTING"))
cards[1].metric("Capital", format_price(s.get("available_capital", 250000)))
cards[2].metric("Open Positions", int(s.get("open_positions", 0) or 0))
cards[3].metric("Daily P&L", format_price(s.get("daily_pnl", 0)))
cards[4].metric("BUY Qualified", int(d.get("buy_qualified", 0) or 0))
cards[5].metric("SELL Qualified", int(d.get("sell_qualified", 0) or 0))
if s.get("message"): st.info(str(s["message"]))

st.subheader("🎯 Strategy 2 — Exact Rules")
st.dataframe(__import__("pandas").DataFrame([
    ("SELL", "Open > PDH → price extends above Open after 09:45 → first completed 1m CLOSE below Open → SELL"),
    ("SELL risk", "SL = Today's High at trigger • Target = PDH"),
    ("BUY", "Open < PDL → price extends below Open after 09:45 → first completed 1m CLOSE above Open → BUY"),
    ("BUY risk", "SL = Today's Low at trigger • Target = PDL"),
    ("Priority", "Largest absolute opening GAP % versus Previous Day Close first"),
    ("Filters", "NIFTY/news are practical protective filters, not multi-indicator gates"),
    ("Capital", "Separate ₹2,50,000 paper account; never mixed with Strategy 1"),
    ("Timing", "30-second control cycle • completed 1-minute strategy candles"),
], columns=["Item", "Rule"]), use_container_width=True, hide_index=True)

st.subheader("📊 Live Strategy 2 State")
st.dataframe(__import__("pandas").DataFrame([
    ("Last scan", s.get("last_scan") or "Not scanned yet"),
    ("Opening candidates", d.get("candidates", 0)),
    ("BUY candidates", d.get("buy_candidates", 0)),
    ("SELL candidates", d.get("sell_candidates", 0)),
    ("BUY qualified", d.get("buy_qualified", 0)),
    ("SELL qualified", d.get("sell_qualified", 0)),
    ("Approved signals", d.get("signals", 0)),
], columns=["Metric", "Value"]), use_container_width=True, hide_index=True)

st.success("Strategy 2 is isolated from Strategy 1: capital, positions, signals, diagnostics and journal are separate.")
st.info("Use the five Strategy 2 pages below through the grouped navigation: Current • Analysis • Scanner • News • Downloads.")
render_daily_footer()
