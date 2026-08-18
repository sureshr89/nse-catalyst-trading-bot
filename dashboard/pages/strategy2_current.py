"""Strategy 2 current trading dashboard.

This page intentionally mirrors the Strategy 1 Current Trading layout and
section order. Only the underlying Strategy 2 data sources and reversal logic differ.
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
from strategy.contracts import strategy_metadata

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"

st.set_page_config(page_title="NSE Catalyst | Strategy 2 Current", page_icon="🎯", layout="wide")
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
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        return max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None


def metric_cards(items):
    html = "<div class='metric-grid'>"
    for label, value in items:
        html += f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


def read_gap_board():
    try:
        return gaps()
    except Exception:
        return pd.DataFrame()


def live_position_values(positions):
    """Return live LTP/P&L for S2 positions using the same calculation as S1.

    This is display-only. It never changes paper state, stops, targets, entries,
    quantities, or any execution decision.
    """
    result = []
    try:
        price_data = PriceData()
    except Exception:
        price_data = None

    for symbol, position in (positions or {}).items():
        ltp = None
        if price_data is not None:
            try:
                latest = price_data.get_latest_market_price(symbol)
                ltp = latest.get("Close") if latest else None
            except Exception:
                ltp = None

        entry = position.get("entry")
        side = str(position.get("signal", "")).upper()
        pnl = None
        try:
            qty = float(position.get("quantity", 0) or 0)
            if ltp is not None and entry is not None and qty:
                if side == "BUY":
                    pnl = (float(ltp) - float(entry)) * qty
                elif side == "SELL":
                    pnl = (float(entry) - float(ltp)) * qty
        except Exception:
            pnl = None

        result.append({
            "Stock": symbol,
            "Strategy": position.get("strategy", "STRATEGY_2"),
            "Side": side,
            "Entry": format_price(entry),
            "LTP": format_price(ltp),
            "Live P&L": format_price(pnl),
            "SL": format_price(position.get("stop_loss")),
            "Target": format_price(position.get("target")),
            "Qty": position.get("quantity", "—"),
            "Risk": format_price(position.get("actual_risk", position.get("risk"))),
            "Entry Time": position.get("entry_time", "—"),
        })
    return result


s = status() or {}
d = diagnostics() or {}
paper = state() or {}
gap = read_gap_board()
sig = signals()
now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
positions = paper.get("open_positions", {}) or {}

worker_age = age_seconds(s.get("heartbeat"))
worker_ok = bool(s.get("worker_alive")) and worker_age is not None and worker_age <= 90
last_scan_age = age_seconds(s.get("last_scan"))
window = "PREPARE" if clock < ENTRY_START else "ACTIVE" if clock <= ENTRY_END else "CLOSED"

st.title("🎯 Strategy 2 — Current Trading")
st.caption(f"Gap Extension Reversal • separate ₹2,50,000 paper account • strategy-driven pipeline • {now.strftime('%d %b %Y %H:%M:%S')} IST")
metric_cards([
    ("SYSTEM WORKER", "🟢 RUNNING" if worker_ok else "🔴 STOPPED / STALE"),
    ("AVAILABLE CAPITAL", format_price(s.get("available_capital", 250000))),
    ("MARKET FILTER", "🟢 ACTIVE" if worker_ok else "⚪ WAIT"),
    ("ENTRY WINDOW", window),
    ("OPEN POSITIONS", len(positions)),
    ("DAILY P&L", format_price(s.get("daily_pnl", 0))),
])

if s.get("last_error"):
    st.error(str(s["last_error"]))

with st.expander("🩺 System & Data Health", expanded=False):
    health = pd.DataFrame([
        ("Worker heartbeat", "PASS" if worker_ok else "FAIL", f"{worker_age}s ago" if worker_age is not None else "missing"),
        ("Scanner diagnostics", "PASS" if last_scan_age is not None and last_scan_age <= 90 else "FAIL", f"{last_scan_age}s ago" if last_scan_age is not None else "missing"),
        ("Opening GAP data", "PASS" if not gap.empty else "FAIL", f"{len(gap)} rows"),
        ("Strategy signals", "PASS" if not sig.empty else "WAIT", f"{len(sig)} records"),
        ("Paper state", "PASS" if isinstance(paper, dict) else "FAIL", f"{len(positions)} open positions"),
        ("Strategy version", "PASS", str(d.get("strategy_version", "unknown"))),
    ], columns=["Check", "Status", "Detail"])
    st.dataframe(health, width="stretch", hide_index=True)

with st.expander("🔗 Decision Pipeline", expanded=False):
    pipeline = pd.DataFrame([
        ("1. Universe", d.get("candidates", 0), "NIFTY 500 opening candidates"),
        ("2. GAP setup", d.get("candidates", 0), "Open above PDH / below PDL"),
        ("3. Extension", d.get("buy_candidates", 0) + d.get("sell_candidates", 0), "Price extends beyond Today's Open"),
        ("4. Reversal trigger", d.get("buy_qualified", 0) + d.get("sell_qualified", 0), "First completed 1m close back through Open"),
        ("5. Risk validation", d.get("risk_adjusted", 0), "₹1,400–₹1,500 actual-risk band"),
        ("6. Approved", d.get("signals", 0), "Risk gate accepted"),
    ], columns=["Stage", "Count", "Meaning"])
    st.dataframe(pipeline, width="stretch", hide_index=True)

st.subheader("📐 Authoritative Strategy Rules")
meta = strategy_metadata("STRATEGY_2")
with st.expander(f"{meta['strategy']} — {meta['name']} — v{meta['version']}", expanded=False):
    rules = list(meta["rules"]) + [
        ("Risk", "₹1,400–₹1,500 actual risk • adaptive target ₹1,450 • minimum 1.25R"),
        ("Entry window", "09:45–14:00 IST"),
        ("Monitoring", "Completed 1-minute strategy candles"),
        ("Square-off", "15:00 IST"),
    ]
    st.dataframe(pd.DataFrame(rules, columns=["Rule", "Definition"]), width="stretch", hide_index=True)

with st.expander("⏳ Waiting & Qualified Stocks", expanded=False):
    waiting = d.get("waiting", {}) or {}
    qualified = d.get("qualified", {}) or {}
    waiting = waiting if isinstance(waiting, dict) else {}
    qualified = qualified if isinstance(qualified, dict) else {}
    waiting_rows = []
    for side in ("BUY", "SELL"):
        side_items = waiting.get(side, {})
        if not isinstance(side_items, dict):
            side_items = {}
        for symbol, item in side_items.items():
            if not isinstance(item, dict):
                continue
            waiting_rows.append({"Side": side, "Stock": symbol, "State": item.get("state", "WAITING"), "Gap %": item.get("gap_percent", 0), "Open": format_price(item.get("today_open")), "PDH": format_price(item.get("pdh")), "PDL": format_price(item.get("pdl"))})
    if waiting_rows:
        wdf = pd.DataFrame(waiting_rows)
        wdf["Gap %"] = pd.to_numeric(wdf["Gap %"], errors="coerce")
        st.dataframe(wdf.sort_values("Gap %", key=lambda x: x.abs(), ascending=False), width="stretch", hide_index=True, height=320)
    else:
        st.info("No Strategy 2 stocks are currently waiting for the next state transition.")

    qualified_rows = []
    for side in ("BUY", "SELL"):
        side_items = qualified.get(side, {})
        if not isinstance(side_items, dict):
            side_items = {}
        for symbol, item in side_items.items():
            if not isinstance(item, dict):
                continue
            qualified_rows.append({"Side": side, "Stock": symbol, "Qualified": item.get("qualified_at", "—"), "Gap %": item.get("gap_percent", 0), "Open": format_price(item.get("today_open")), "PDH": format_price(item.get("pdh")), "PDL": format_price(item.get("pdl"))})
    if qualified_rows:
        qdf = pd.DataFrame(qualified_rows)
        qdf["Gap %"] = pd.to_numeric(qdf["Gap %"], errors="coerce")
        st.dataframe(qdf.sort_values("Gap %", key=lambda x: x.abs(), ascending=False), width="stretch", hide_index=True, height=260)
    else:
        st.info("No Strategy 2 candidate has completed its extension → reversal sequence yet.")

with st.expander("🏆 Gap Board — Largest Absolute Gap First", expanded=False):
    if gap.empty:
        st.info("Strategy 2 GAP board has not been prepared yet.")
    else:
        board = gap.copy()
        for c in ["TodayOpen", "PDH", "PDL", "Gap", "GapPercentFromPreviousClose"]:
            if c in board.columns:
                board[c] = pd.to_numeric(board[c], errors="coerce")
        if "GapPercentFromPreviousClose" in board.columns:
            board["Priority"] = board["GapPercentFromPreviousClose"].abs()
            board = board.sort_values("Priority", ascending=False)
        cols = [c for c in ["Symbol", "TodayOpen", "PDH", "PDL", "PreviousDayClose", "Gap", "GapPercentFromPreviousClose", "GapType", "OpeningSetup"] if c in board.columns]
        view = board[cols].head(50).copy()
        for c in ["TodayOpen", "PDH", "PDL", "PreviousDayClose", "Gap"]:
            if c in view.columns:
                view[c] = view[c].map(format_price)
        for c in ["GapPercentFromPreviousClose"]:
            if c in view.columns:
                view[c] = view[c].map(format_pct)
        st.dataframe(view, width="stretch", hide_index=True, height=360)

with st.expander("🚨 Today's Approved Signals", expanded=False):
    if not sig.empty:
        frame = sig.copy()
        cols = [c for c in ["strategy", "strategy_version", "symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_reward", "gap_percent", "priority_rank"] if c in frame.columns]
        if cols:
            st.dataframe(frame[cols].tail(25).iloc[::-1], width="stretch", hide_index=True)
        else:
            st.dataframe(frame.tail(25).iloc[::-1], width="stretch", hide_index=True)
    else:
        st.info("No Strategy 2 approved signals yet.")

st.subheader("📍 Open Paper Positions")
if positions:
    rows = live_position_values(positions)
    st.dataframe(pd.DataFrame(rows).astype(str), width="stretch", hide_index=True)
else:
    st.info("No open Strategy 2 paper positions.")

st.caption(f"Worker heartbeat: {s.get('heartbeat', '—')} • Last scan: {s.get('last_scan', '—')} • Last error: {s.get('last_error') or 'None'} • Auto-refresh 5s • Paper trading only")
render_daily_footer()
