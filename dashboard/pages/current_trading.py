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


def cards(items):
    html = "<div class='metric-grid'>"
    for label, value in items:
        html += f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def price(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "—"


def pct(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "—"


status = read(ROOT / "outputs/bot_status.json")
state = read(ROOT / "outputs/paper_engine_state.json")
diag = read(ROOT / "outputs/scanner_diagnostics.json")
gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
trades = read(ROOT / "outputs/trades.csv", "csv")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

try:
    live = ensure_bot_running()
    if isinstance(live, dict):
        status.update(live)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
market_change = float(diag.get("nifty500_change_pct", 0) or 0) if isinstance(diag, dict) else 0.0

if market_change >= NIFTY_THRESHOLD:
    permission = "🟢 BUY"
    permission_note = "NIFTY 500 supports long setups"
elif market_change <= -NIFTY_THRESHOLD:
    permission = "🔴 SELL"
    permission_note = "NIFTY 500 supports short setups"
else:
    permission = "⚪ WAIT"
    permission_note = "NIFTY 500 filter not satisfied"

if clock < ENTRY_START:
    window = "PREPARE"
elif clock <= ENTRY_END:
    window = "ACTIVE"
else:
    window = "CLOSED"

st.title("🎯 Current Trading")
st.caption("Live strategy command center • only actionable information for today's entries")

cards([
    ("NIFTY 500", pct(market_change)),
    ("Market Permission", permission),
    ("Entry Window", window),
    ("Open Positions", len(positions)),
])
st.caption(f"{permission_note} • {ENTRY_START}–{ENTRY_END} IST • Updated {now.strftime('%H:%M:%S')} IST")

if status.get("error"):
    st.warning(str(status["error"]))

# Strategy state: concise, visual and based on the exact new rules.
st.subheader("⚡ Live Strategy State")
strategy_rows = [
    ("Universe", "NIFTY 500"),
    ("Timeframe", "1-minute completed prices"),
    ("BUY", "Open > PDH → close below PDH → reversal candle Open < Today's Open < Close"),
    ("SELL", "Open < PDL → close above PDL → reversal candle Open > Today's Open > Close"),
    ("Market filter", "BUY ≥ +0.25% • SELL ≤ −0.25%"),
    ("Entry", "Close of qualifying 1-minute reversal candle"),
]
st.dataframe(pd.DataFrame(strategy_rows, columns=["Condition", "Current Rule"]), width="stretch", hide_index=True)

st.subheader("🎯 Candidates")
if not gaps.empty and "GapType" in gaps.columns:
    board = gaps.copy()
    for col in ["TodayOpen", "PDH", "PDL", "Gap", "GapPercent"]:
        if col in board.columns:
            board[col] = pd.to_numeric(board[col], errors="coerce")

    ups = board[board["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False)
    downs = board[board["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")
    cards([("BUY Candidates", len(ups)), ("SELL Candidates", len(downs)), ("Total", len(ups) + len(downs))])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### 🟢 BUY WATCHLIST")
        st.caption("Today's Open above PDH — waiting for PDH breach/reaction and reversal through Today's Open")
        if ups.empty:
            st.info("No BUY candidates currently.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDH", "GapPercent"] if c in ups.columns]
            view = ups[cols].head(30).copy()
            for col in ["TodayOpen", "PDH"]:
                if col in view.columns:
                    view[col] = view[col].map(price)
            if "GapPercent" in view.columns:
                view["GapPercent"] = view["GapPercent"].map(pct)
            st.dataframe(view, width="stretch", hide_index=True, height=360)

    with c2:
        st.markdown("### 🔴 SELL WATCHLIST")
        st.caption("Today's Open below PDL — waiting for PDL breach/reaction and reversal through Today's Open")
        if downs.empty:
            st.info("No SELL candidates currently.")
        else:
            cols = [c for c in ["Symbol", "TodayOpen", "PDL", "GapPercent"] if c in downs.columns]
            view = downs[cols].head(30).copy()
            for col in ["TodayOpen", "PDL"]:
                if col in view.columns:
                    view[col] = view[col].map(price)
            if "GapPercent" in view.columns:
                view["GapPercent"] = view["GapPercent"].map(pct)
            st.dataframe(view, width="stretch", hide_index=True, height=360)
else:
    st.info("Candidates will populate automatically when today's market data is available.")

st.subheader("🚨 Active Signals")
if not trades.empty:
    recent = trades.tail(20).copy()
    preferred = ["symbol", "signal", "entry_time", "entry", "stop_loss", "target", "market_direction", "stock_direction"]
    cols = [c for c in preferred if c in recent.columns]
    if cols:
        st.dataframe(recent[cols].iloc[::-1], width="stretch", hide_index=True, height=260)
    else:
        st.info("No displayable signals yet.")
else:
    st.info("No qualifying signals yet. The bot will show a stock here only after every strategy condition is satisfied.")

st.subheader("📍 Open Positions")
if positions:
    price_data = PriceData()
    rows = []
    for symbol, position in positions.items():
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
            if ltp is not None and entry is not None:
                pnl = (float(ltp) - float(entry)) * qty if side == "BUY" else (float(entry) - float(ltp)) * qty
        except Exception:
            pass
        rows.append({
            "Stock": symbol,
            "Side": side,
            "Entry": price(entry),
            "LTP": price(ltp),
            "Live P&L": price(pnl),
            "SL": price(position.get("stop_loss")),
            "Target": price(position.get("target")),
            "Qty": position.get("quantity", "—"),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open paper positions.")

st.caption("Auto-refresh: 5 seconds • Paper trading only")
render_daily_footer()
