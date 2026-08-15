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

st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="🎯", layout="wide")
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


def fmt_number(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "—"


status = read(ROOT / "outputs/bot_status.json")
state = read(ROOT / "outputs/paper_engine_state.json")
gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
diag = read(ROOT / "outputs/scanner_diagnostics.json")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

try:
    live_status = ensure_bot_running()
    if isinstance(live_status, dict):
        status.update(live_status)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
market_change = float(diag.get("nifty500_change_pct", 0) or 0) if isinstance(diag, dict) else 0.0

if market_change >= NIFTY_THRESHOLD:
    permission = "🟢 BUY ONLY"
    permission_note = "NIFTY 500 ≥ +0.25%"
elif market_change <= -NIFTY_THRESHOLD:
    permission = "🔴 SELL ONLY"
    permission_note = "NIFTY 500 ≤ −0.25%"
else:
    permission = "⚪ WAIT"
    permission_note = "NIFTY 500 inside −0.25% to +0.25%"

if clock < ENTRY_START:
    window = "🕘 PREPARE"
elif clock <= ENTRY_END:
    window = "🟢 ACTIVE"
else:
    window = "🔒 CLOSED"

st.title("🎯 Current Trading")
st.caption("Live trade command center • only information that affects today's entries and open positions")

metric_cards([
    ("NIFTY 500", fmt_number(market_change)),
    ("Permission", permission),
    ("Entry Window", window),
    ("Positions", len(positions)),
])
st.caption(f"{permission_note} • Entry window {ENTRY_START}–{ENTRY_END} IST • Updated {now.strftime('%H:%M:%S')} IST")

if status.get("error"):
    st.warning(str(status["error"]))

with st.expander("How a setup becomes a trade", expanded=False):
    st.markdown(
        "**BUY:** Today's Open > PDH → price first closes below PDH → later one completed 1-minute candle "
        "opens below Today's Open and closes above Today's Open. NIFTY 500 must be ≥ +0.25%.\n\n"
        "**SELL:** Today's Open < PDL → price first closes above PDL → later one completed 1-minute candle "
        "opens above Today's Open and closes below Today's Open. NIFTY 500 must be ≤ −0.25%.\n\n"
        "The entry is taken at the qualifying 1-minute candle close. Entries are allowed only from 09:45 to 14:00 IST."
    )

st.subheader("🎯 Today's Opening Setups")

if not gaps.empty and "GapType" in gaps.columns:
    board = gaps.copy()
    board["GapPercent"] = pd.to_numeric(board.get("GapPercent"), errors="coerce")
    board["Gap"] = pd.to_numeric(board.get("Gap"), errors="coerce")

    ups = board[board["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False)
    downs = board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f"### 🟢 BUY setups  ·  {len(ups)}")
        st.caption("Open > PDH → close below PDH → 1m candle opens below Today's Open and closes above it")
        if ups.empty:
            st.info("No gap-up setups.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDH", "Gap", "GapPercent"] if c in ups.columns]
            display = ups[cols].head(30).copy()
            for col in ["TodayOpen", "PDH", "Gap"]:
                if col in display.columns:
                    display[col] = pd.to_numeric(display[col], errors="coerce").map(fmt_price)
            if "GapPercent" in display.columns:
                display["GapPercent"] = display["GapPercent"].map(fmt_number)
            st.dataframe(display, width="stretch", hide_index=True, height=350)

    with c2:
        st.markdown(f"### 🔴 SELL setups  ·  {len(downs)}")
        st.caption("Open < PDL → close above PDL → 1m candle opens above Today's Open and closes below it")
        if downs.empty:
            st.info("No gap-down setups.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDL", "Gap", "GapPercent"] if c in downs.columns]
            display = downs[cols].head(30).copy()
            for col in ["TodayOpen", "PDL", "Gap"]:
                if col in display.columns:
                    display[col] = pd.to_numeric(display[col], errors="coerce").map(fmt_price)
            if "GapPercent" in display.columns:
                display["GapPercent"] = display["GapPercent"].map(fmt_number)
            st.dataframe(display, width="stretch", hide_index=True, height=350)
else:
    st.info("Today's opening setup board will appear automatically once market data is available after 09:15 IST.")

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
    st.info("No open paper positions.")

st.caption("Auto-refresh: 5 seconds • Paper trading only")
render_daily_footer()
