"""Strategy 2 live command center.

The standalone Strategy 2 Scanner page is intentionally removed from navigation.
The operator-facing scanner summary is kept here with the current positions.
"""
from pathlib import Path
import sys
from datetime import datetime, timezone
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
from dashboard.strategy2_data import status, diagnostics, state, gaps, signals, format_price, format_pct
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Current", page_icon="🔴", layout="wide")
st_autorefresh(interval=5000, key="s2_current_live")
st.markdown(load_css(), unsafe_allow_html=True)
try:
    ensure_bot_running()
except Exception:
    pass
render_nav()


def age_seconds(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=INDIA_TZ) if stamp.tzinfo is None else stamp
        return max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None


def cards(items):
    st.markdown("<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items) + "</div>", unsafe_allow_html=True)

s = status() or {}
d = diagnostics() or {}
paper = state() or {}
gap = gaps()
sig = signals()
now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
positions = paper.get("open_positions", {}) or {}
worker_age = age_seconds(s.get("heartbeat"))
scan_age = age_seconds(d.get("timestamp"))
worker_ok = bool(s.get("worker_alive")) and worker_age is not None and worker_age <= 90
window = "PREPARE" if clock < ENTRY_START else "ACTIVE" if clock <= ENTRY_END else "CLOSED"

st.title("🔴 Strategy 2 — Current Trading")
st.caption(f"Gap Extension Reversal • separate ₹2,50,000 paper account • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([
    ("WORKER", "🟢 RUNNING" if worker_ok else "🔴 STALE"),
    ("AVAILABLE CAPITAL", format_price(s.get("available_capital", 250000))),
    ("ENTRY WINDOW", window),
    ("OPEN POSITIONS", len(positions)),
    ("DAILY P&L", format_price(s.get("daily_pnl", 0))),
    ("LAST SCAN", f"{scan_age}s ago" if scan_age is not None else "—"),
])
if s.get("last_error"):
    st.error(str(s["last_error"]))

st.subheader("🔎 Scanner — Live Summary")
cards([
    ("CANDIDATES", d.get("candidates", 0)),
    ("BUY CANDIDATES", d.get("buy_candidates", 0)),
    ("SELL CANDIDATES", d.get("sell_candidates", 0)),
    ("BUY QUALIFIED", d.get("buy_qualified", 0)),
    ("SELL QUALIFIED", d.get("sell_qualified", 0)),
    ("APPROVED", d.get("signals", 0)),
    ("RISK ADJUSTED", d.get("risk_adjusted", 0)),
    ("REJECTIONS", sum((d.get("rejections", {}) or {}).values())),
])

with st.expander("📋 Scanner Pipeline", expanded=False):
    pipeline = pd.DataFrame([
        ("NIFTY 500 opening candidates", d.get("candidates", 0), "Gap above PDH / below PDL"),
        ("Extension candidates", int(d.get("buy_candidates", 0) or 0) + int(d.get("sell_candidates", 0) or 0), "Move beyond Today's Open"),
        ("Reversal qualified", int(d.get("buy_qualified", 0) or 0) + int(d.get("sell_qualified", 0) or 0), "Return through Today's Open"),
        ("Risk adjusted", d.get("risk_adjusted", 0), "₹1,400–₹1,500 actual-risk band"),
        ("Final approved", d.get("signals", 0), "Risk gate accepted"),
    ], columns=["Stage", "Count", "Meaning"])
    st.dataframe(pipeline, width="stretch", hide_index=True)

with st.expander("🏆 Top Scanner Candidates", expanded=False):
    if gap.empty:
        st.info("No Strategy 2 gap data yet.")
    else:
        board = gap.copy()
        for c in ["TodayOpen", "PDH", "PDL", "PreviousDayClose", "Gap", "GapPercentFromPreviousClose"]:
            if c in board.columns:
                board[c] = pd.to_numeric(board[c], errors="coerce")
        if "GapPercentFromPreviousClose" in board.columns:
            board["Priority"] = board["GapPercentFromPreviousClose"].abs()
            board = board.sort_values("Priority", ascending=False)
        cols = [c for c in ["Symbol", "TodayOpen", "PDH", "PDL", "GapPercentFromPreviousClose", "GapType", "OpeningSetup"] if c in board.columns]
        view = board[cols].head(30).copy()
        for c in ["TodayOpen", "PDH", "PDL"]:
            if c in view.columns: view[c] = view[c].map(format_price)
        if "GapPercentFromPreviousClose" in view.columns: view["GapPercentFromPreviousClose"] = view["GapPercentFromPreviousClose"].map(format_pct)
        st.dataframe(view, width="stretch", hide_index=True, height=330)

with st.expander("🚨 Today's Approved Signals", expanded=False):
    if not sig.empty:
        cols = [c for c in ["symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_reward", "gap_percent", "priority_rank"] if c in sig.columns]
        st.dataframe(sig[cols].tail(20).iloc[::-1] if cols else sig.tail(20).iloc[::-1], width="stretch", hide_index=True)
    else:
        st.info("No Strategy 2 approved signals today.")

st.subheader("📍 Open Paper Positions")
if positions:
    rows = []
    pdx = PriceData()
    for symbol, position in positions.items():
        try:
            latest = pdx.get_latest_live_price(symbol, max_age_seconds=3)
            ltp = latest.get("Close") if latest else None
        except Exception:
            ltp = None
        entry = position.get("entry"); side = str(position.get("signal", "")).upper(); pnl = None
        try:
            qty = float(position.get("quantity", 0) or 0)
            if ltp is not None and entry is not None:
                pnl = ((float(ltp) - float(entry)) * qty) if side == "BUY" else ((float(entry) - float(ltp)) * qty)
        except Exception: pass
        rows.append({"Stock": symbol, "Side": side, "Entry": format_price(entry), "LTP": format_price(ltp), "Live P&L": format_price(pnl), "SL": format_price(position.get("stop_loss")), "Target": format_price(position.get("target")), "Qty": position.get("quantity", "—"), "Entry Time": position.get("entry_time", "—")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open Strategy 2 paper positions.")

st.caption(f"Heartbeat: {s.get('heartbeat','—')} • Last scan: {d.get('timestamp','—')} • Position exit monitor: every ~2s • UI refresh: 5s")
render_daily_footer()
