import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="📌", layout="wide")
st_autorefresh(interval=5000, key="current_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def read(path, kind="json"):
    try:
        return json.loads(path.read_text()) if kind == "json" else pd.read_csv(path)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def metric_cards(items):
    html = "<div class='metric-grid'>"
    for label, value in items:
        html += f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def fmt_price(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "—"


status = read(ROOT / "outputs/bot_status.json")
state = read(ROOT / "outputs/paper_engine_state.json")
gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
trades = read(ROOT / "outputs/trades.csv", "csv")
diag = read(ROOT / "outputs/scanner_diagnostics.json")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

# Keep the worker alive, but do not turn this page into a Bot Status page.
try:
    live_status = ensure_bot_running()
    if isinstance(live_status, dict):
        status.update(live_status)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

market_change = float(diag.get("nifty500_change_pct", 0) or 0) if isinstance(diag, dict) else 0.0
if market_change >= 0.25:
    market_side = "🟢 BUY ONLY"
elif market_change <= -0.25:
    market_side = "🔴 SELL ONLY"
else:
    market_side = "⚪ NO ENTRY"

st.title("📌 Current Trading")
st.caption("Action board • NIFTY 500 filter → PDH/PDL opening setup → fresh 1-minute price reversal")

# One compact decision strip: only information that changes the trading decision.
metric_cards([
    ("NIFTY 500", f"{market_change:+.2f}%"),
    ("Market Permission", market_side),
    ("Entry Window", "09:45–14:00"),
    ("Open Positions", len(positions)),
])

if status.get("error"):
    st.warning(str(status["error"]))

st.subheader("🎯 How the bot is looking for trades")
left, right = st.columns(2, gap="large")
with left:
    st.markdown("**🟢 BUY setup**")
    st.markdown("1. Today's Open is **above PDH**\n2. Price reacts down to **PDH**\n3. Later, a fresh 1-minute price crosses back **above Today's Open**\n4. NIFTY 500 must be **≥ +0.25%**")
with right:
    st.markdown("**🔴 SELL setup**")
    st.markdown("1. Today's Open is **below PDL**\n2. Price reacts up to **PDL**\n3. Later, a fresh 1-minute price crosses back **below Today's Open**\n4. NIFTY 500 must be **≤ −0.25%**")
st.caption("No candle-pattern confirmation. Entry is based on the actual qualifying 1-minute price sequence.")

st.subheader("📋 Opening Setup Board")
if not gaps.empty and "GapType" in gaps.columns:
    board = gaps.copy()
    board["GapPercent"] = pd.to_numeric(board.get("GapPercent"), errors="coerce")
    ups = board[board["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False)
    downs = board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**🟢 BUY candidates — Open > PDH**")
        if ups.empty:
            st.info("No gap-up candidates.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDH", "Gap", "GapPercent"] if c in ups.columns]
            st.dataframe(ups[cols].head(25), width="stretch", hide_index=True, height=330)
    with c2:
        st.markdown("**🔴 SELL candidates — Open < PDL**")
        if downs.empty:
            st.info("No gap-down candidates.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDL", "Gap", "GapPercent"] if c in downs.columns]
            st.dataframe(downs[cols].head(25), width="stretch", hide_index=True, height=330)
else:
    st.info("Opening setup board will populate from the first available market data after 09:15 IST.")

st.subheader("📍 Open Positions")
if positions:
    price = PriceData()
    rows = []
    for symbol, position in positions.items():
        try:
            latest = price.get_latest_market_price(symbol)
            ltp = latest.get("Close") if latest else None
        except Exception:
            ltp = None
        entry = position.get("entry")
        side = str(position.get("signal", "")).upper()
        pnl = None
        try:
            qty = float(position.get("quantity", 0) or 0)
            if ltp is not None and entry is not None:
                pnl = (float(ltp) - float(entry)) * qty if side == "BUY" else (float(entry) - float(ltp)) * qty
        except Exception:
            pass
        rows.append({
            "Stock": symbol,
            "Side": side,
            "Entry": fmt_price(entry),
            "LTP": fmt_price(ltp),
            "Live P&L": fmt_price(pnl) if pnl is not None else "—",
            "SL": fmt_price(position.get("stop_loss")),
            "Target": fmt_price(position.get("target")),
            "Qty": position.get("quantity", "—"),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open paper positions. New qualifying setups will appear here automatically.")

st.subheader("🔎 Scanner Snapshot")
if isinstance(diag, dict) and diag:
    metric_cards([
        ("Stocks Scanned", diag.get("stocks_scanned", 0)),
        ("1-min Coverage", f"{float(diag.get('market_data_coverage', 0) or 0) * 100:.1f}%"),
        ("Gap Up", diag.get("gap_up_count", 0)),
        ("Gap Down", diag.get("gap_down_count", 0)),
        ("Strategy Matches", diag.get("strategy_setup_passed", 0)),
        ("Final Signals", diag.get("final_signals", 0)),
    ])
else:
    st.info("Scanner snapshot will appear after the next scan.")

st.subheader("🧾 Latest Trade Result")
if not trades.empty and "status" in trades.columns:
    closed = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    closed = pd.DataFrame()

if not closed.empty:
    t = closed.iloc[-1]
    pnl = pd.to_numeric(pd.Series([t.get("pnl", 0)]), errors="coerce").fillna(0).iloc[0]
    metric_cards([
        ("Stock", t.get("symbol", "—")),
        ("Side", t.get("signal", "—")),
        ("Entry", fmt_price(t.get("entry"))),
        ("Exit", fmt_price(t.get("exit_price"))),
        ("P&L", fmt_price(pnl)),
        ("Reason", t.get("exit_reason", "—")),
    ])
else:
    st.info("No closed paper trade yet.")

render_daily_footer()
