"""Strategy 2 stock scanner.

Layout intentionally mirrors Strategy 1 Stock Scanner. Strategy 2 keeps its
own data source and reversal logic, but the page structure is the same.
"""
from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from dashboard.strategy2_data import status, diagnostics, gaps, state, signals, format_price, format_pct

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Scanner", page_icon="🔎", layout="wide")
st_autorefresh(interval=5000, key="s2_scanner_live")
st.markdown(load_css(), unsafe_allow_html=True)
try:
    ensure_bot_running()
except Exception:
    pass
render_nav()

s = status() or {}
d = diagnostics() or {}
gap = gaps()
paper = state() or {}
positions = paper.get("open_positions", {}) or {}
now = datetime.now(INDIA_TZ)

waiting = d.get("waiting", {}) or {}
qualified = d.get("qualified", {}) or {}

st.title("🔎 Strategy 2 — Stock Scanner")
st.caption("Workflow: highest qualifying GAP first → extension → reversal → strategy/risk validation → paper entry")

metric_cards = [
    ("BUY waiting", len(waiting.get("BUY", {}) or {})),
    ("SELL waiting", len(waiting.get("SELL", {}) or {})),
    ("BUY qualified", len(qualified.get("BUY", {}) or {})),
    ("SELL qualified", len(qualified.get("SELL", {}) or {})),
]
html = "<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a, b in metric_cards) + "</div>"
st.markdown(html, unsafe_allow_html=True)
st.caption(f"Strategy 2 • 1-minute completed-candle reversal logic • Updated {now.strftime('%H:%M:%S')} IST")

with st.expander("🏆 Priority Ranking — Highest Gap First", expanded=False):
    ranks = pd.DataFrame(d.get("ranking", []) if isinstance(d, dict) else [])
    if ranks.empty and not gap.empty:
        ranks = gap.copy()
        if "GapPercentFromPreviousClose" in ranks.columns:
            ranks["Gap %"] = pd.to_numeric(ranks["GapPercentFromPreviousClose"], errors="coerce")
            ranks["Priority"] = ranks["Gap %"].abs()
            ranks = ranks.sort_values("Priority", ascending=False)
            view = ranks[[c for c in ["Symbol", "Gap %", "GapType", "OpeningSetup"] if c in ranks.columns]].head(100).copy()
            if "Gap %" in view.columns:
                view["Gap %"] = view["Gap %"].map(format_pct)
            st.dataframe(view, width="stretch", hide_index=True, height=360)
        else:
            st.info("No qualified candidates yet.")
    elif not ranks.empty:
        for col in ["gap_percent", "gap_priority_pct"]:
            if col in ranks.columns:
                ranks[col] = pd.to_numeric(ranks[col], errors="coerce")
        if "gap_percent" in ranks.columns:
            ranks = ranks.sort_values("gap_percent", key=lambda x: x.abs(), ascending=False)
        display_cols = [c for c in ["priority", "symbol", "side", "gap_percent", "candidate_state"] if c in ranks.columns]
        view = ranks[display_cols].copy()
        view.rename(columns={"priority": "Priority", "symbol": "Symbol", "side": "Side", "gap_percent": "Gap %", "candidate_state": "State"}, inplace=True)
        if "Gap %" in view.columns:
            view["Gap %"] = view["Gap %"].map(format_pct)
        st.dataframe(view, width="stretch", hide_index=True, height=360)
        st.caption("Priority is determined by the largest qualifying absolute GAP %. No secondary volatility metric is used.")
    else:
        st.info("No qualified candidates yet.")

with st.expander("⏳ Waiting Stocks", expanded=False):
    rows = []
    for side in ("BUY", "SELL"):
        for symbol, item in (waiting.get(side, {}) or {}).items():
            rows.append({"Side": side, "Symbol": symbol, "State": item.get("state", "WAITING"), "Gap %": item.get("gap_percent", 0), "Today's Open": format_price(item.get("today_open")), "PDH": format_price(item.get("pdh")), "PDL": format_price(item.get("pdl")), "Created": item.get("created_at", "—")})
    if rows:
        wdf = pd.DataFrame(rows)
        wdf["Gap %"] = pd.to_numeric(wdf["Gap %"], errors="coerce")
        st.dataframe(wdf.sort_values("Gap %", key=lambda x: x.abs(), ascending=False), width="stretch", hide_index=True, height=360)
    else:
        st.info("No stocks are currently waiting for the required extension/reversal sequence.")

with st.expander("📊 Gap / Opening Board", expanded=False):
    if gap.empty:
        st.info("Strategy 2 GAP board will appear when market data is available.")
    else:
        board = gap.copy()
        if "GapPercentFromPreviousClose" in board.columns:
            board["GapPercentFromPreviousClose"] = pd.to_numeric(board["GapPercentFromPreviousClose"], errors="coerce")
            board["GapPriority"] = board["GapPercentFromPreviousClose"].abs()
            board = board.sort_values("GapPriority", ascending=False, na_position="last")
        preferred = [c for c in ["Symbol", "TodayOpen", "PreviousDayClose", "PDH", "PDL", "Gap", "GapPercentFromPreviousClose", "GapType", "OpeningSetup"] if c in board.columns]
        view = board[preferred].copy()
        for c in ["TodayOpen", "PreviousDayClose", "PDH", "PDL", "Gap"]:
            if c in view.columns:
                view[c] = view[c].map(format_price)
        if "GapPercentFromPreviousClose" in view.columns:
            view["GapPercentFromPreviousClose"] = view["GapPercentFromPreviousClose"].map(format_pct)
        st.dataframe(view, width="stretch", hide_index=True, height=520)

st.subheader("📍 Open Paper Positions")
if positions:
    rows = []
    for symbol, p in positions.items():
        rows.append({"Stock": symbol, "Strategy": p.get("strategy", "STRATEGY_2"), "Side": p.get("signal"), "Entry": format_price(p.get("entry")), "SL": format_price(p.get("stop_loss")), "Target": format_price(p.get("target")), "Qty": p.get("quantity"), "Risk": format_price(p.get("actual_risk", p.get("risk"))), "Entry Time": p.get("entry_time", "—")})
    st.dataframe(pd.DataFrame(rows).astype(str), width="stretch", hide_index=True)
else:
    st.info("No open Strategy 2 paper positions.")

st.caption("Strategy: qualifying gap → extension beyond Today's Open → first completed 1-minute CLOSE back through Today's Open → risk validation. Paper trading only.")
render_daily_footer()
