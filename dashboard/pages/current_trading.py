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
ENTRY_START = "09:45"
ENTRY_END = "14:00"
NIFTY_THRESHOLD = 0.25

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

# This page needs the worker running, but worker diagnostics belong on Bot Status.
try:
    live_status = ensure_bot_running()
    if isinstance(live_status, dict):
        status.update(live_status)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

market_change = float(diag.get("nifty500_change_pct", 0) or 0) if isinstance(diag, dict) else 0.0
if market_change >= NIFTY_THRESHOLD:
    market_permission = "BUY ONLY"
    market_icon = "🟢"
elif market_change <= -NIFTY_THRESHOLD:
    market_permission = "SELL ONLY"
    market_icon = "🔴"
else:
    market_permission = "NO ENTRY"
    market_icon = "⚪"

now_ist = datetime.now(INDIA_TZ)
clock = now_ist.strftime("%H:%M:%S")

st.title("📌 Current Trading")
st.caption("Live action board — only the information needed to decide whether a setup is eligible.")

# Primary decision strip.
metric_cards([
    ("NIFTY 500", f"{market_change:+.2f}%"),
    ("Permission", f"{market_icon} {market_permission}"),
    ("Entry Window", f"{ENTRY_START}–{ENTRY_END}"),
    ("Open Positions", len(positions)),
    ("Updated", clock),
])

if status.get("error"):
    st.warning(str(status["error"]))

# Keep the strategy explanation short and visible, without turning this into documentation.
with st.expander("Strategy rules", expanded=False):
    st.markdown(
        "**BUY:** Today's Open > PDH → price reaches/reacts from PDH → later price crosses above Today's Open. "
        "NIFTY 500 must be ≥ +0.25%.\n\n"
        "**SELL:** Today's Open < PDL → price reaches/reacts from PDL → later price crosses below Today's Open. "
        "NIFTY 500 must be ≤ −0.25%.\n\n"
        "Entry uses the actual qualifying 1-minute price. No candle-pattern confirmation. "
        "Entries are allowed only from 09:45 to 14:00 IST."
    )

# Opening candidates are the main research/trading board.
st.subheader("🎯 Opening Setup Board")
if not gaps.empty and "GapType" in gaps.columns:
    board = gaps.copy()
    board["GapPercent"] = pd.to_numeric(board.get("GapPercent"), errors="coerce")
    board["Gap"] = pd.to_numeric(board.get("Gap"), errors="coerce")

    ups = board[board["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False)
    downs = board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")

    metric_cards([
        ("Gap Up / BUY", len(ups)),
        ("Gap Down / SELL", len(downs)),
        ("Total Setups", len(ups) + len(downs)),
    ])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**🟢 BUY side — Open > PDH**")
        if ups.empty:
            st.info("No BUY-side opening setups.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDH", "Gap", "GapPercent"] if c in ups.columns]
            display = ups[cols].head(30).copy()
            if "TodayOpen" in display.columns:
                display["TodayOpen"] = pd.to_numeric(display["TodayOpen"], errors="coerce").round(2)
            if "PDH" in display.columns:
                display["PDH"] = pd.to_numeric(display["PDH"], errors="coerce").round(2)
            st.dataframe(display, width="stretch", hide_index=True, height=360)

    with c2:
        st.markdown("**🔴 SELL side — Open < PDL**")
        if downs.empty:
            st.info("No SELL-side opening setups.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDL", "Gap", "GapPercent"] if c in downs.columns]
            display = downs[cols].head(30).copy()
            if "TodayOpen" in display.columns:
                display["TodayOpen"] = pd.to_numeric(display["TodayOpen"], errors="coerce").round(2)
            if "PDL" in display.columns:
                display["PDL"] = pd.to_numeric(display["PDL"], errors="coerce").round(2)
            st.dataframe(display, width="stretch", hide_index=True, height=360)
else:
    st.info("The opening setup board will populate automatically after 09:15 IST when today's market data is available.")

# Only live positions are shown here. Detailed execution history belongs on Analysis/Downloads.
st.subheader("📍 Live Positions")
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
    st.info("No open paper positions.")

# A compact diagnostic footer is useful when the page looks empty, but avoids the old large filter dashboard.
if isinstance(diag, dict) and diag:
    st.caption(
        f"Scanner: {diag.get('stocks_scanned', 0)} stocks • "
        f"1-min coverage {float(diag.get('market_data_coverage', 0) or 0) * 100:.1f}% • "
        f"{diag.get('final_signals', 0)} final signal(s) • auto-refresh 5s"
    )

render_daily_footer()
