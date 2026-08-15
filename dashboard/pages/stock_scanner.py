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

INDIA_TZ = ZoneInfo("Asia/Kolkata")
NIFTY_THRESHOLD = 0.25
ENTRY_START = "09:45"
ENTRY_END = "14:00"

st.set_page_config(page_title="NSE Catalyst | Stock Scanner", page_icon="🔎", layout="wide")
st_autorefresh(interval=5000, key="stock_scanner_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def money(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "—"


def pct(value):
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "—"


gaps = read_csv(ROOT / "outputs/gap_analysis.csv")
signals = read_csv(ROOT / "outputs/signals.csv")
state = read_json(ROOT / "outputs/paper_engine_state.json")
status = read_json(ROOT / "outputs/bot_status.json")
diag = read_json(ROOT / "outputs/scanner_diagnostics.json")

try:
    live = ensure_bot_running()
    if isinstance(live, dict):
        status.update(live)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
market_change = float(diag.get("nifty500_change_pct", 0) or 0) if isinstance(diag, dict) else 0.0
now = datetime.now(INDIA_TZ)

st.title("🔎 NIFTY 500 Stock Scanner")
st.caption("Complete stock-by-stock view • gap status • strategy progress • entry status")
if status.get("error"):
    st.warning(str(status["error"]))
if gaps.empty:
    st.info("Complete stock data will appear when the market data feed populates gap_analysis.csv.")
    render_daily_footer()
    st.stop()

board = gaps.copy()
for col in ["TodayOpen", "PDH", "PDL", "Gap", "GapPercent"]:
    if col in board.columns:
        board[col] = pd.to_numeric(board[col], errors="coerce")

position_symbols = {str(s).upper() for s in positions.keys()}
latest_signal = {}
if not signals.empty and "symbol" in signals.columns:
    ordered = signals.copy()
    if "timestamp" in ordered.columns:
        ordered = ordered.sort_values("timestamp")
    for _, row in ordered.iterrows():
        latest_signal[str(row.get("symbol", "")).upper()] = row.to_dict()

approved_symbols = set()
for symbol, record in latest_signal.items():
    approved = str(record.get("approved", "")).lower() in {"true", "1", "yes"}
    if approved:
        approved_symbols.add(symbol)


def stock_status(row):
    symbol = str(row.get("Symbol", "")).upper()
    gap_type = str(row.get("GapType", ""))
    record = latest_signal.get(symbol, {})
    if symbol in position_symbols:
        return "🟢 ENTERED"
    if symbol in approved_symbols:
        return "🔵 QUALIFIED / NOT ENTERED"
    if record and str(record.get("reason", "")).strip():
        return "🔴 NOT QUALIFIED"
    if gap_type == "GAP_UP":
        return "🟡 GAP UP / WAITING" if market_change >= NIFTY_THRESHOLD else "🔴 GAP UP / NIFTY FILTER"
    if gap_type == "GAP_DOWN":
        return "🟠 GAP DOWN / WAITING" if market_change <= -NIFTY_THRESHOLD else "🔴 GAP DOWN / NIFTY FILTER"
    return "⚪ WAITING"


board["Status"] = board.apply(stock_status, axis=1)
board["NIFTY 500"] = "BUY" if market_change >= NIFTY_THRESHOLD else "SELL" if market_change <= -NIFTY_THRESHOLD else "WAIT"


def reason(row):
    symbol = str(row.get("Symbol", "")).upper()
    record = latest_signal.get(symbol, {})
    recorded = str(record.get("reason", "")).strip()
    status_text = row["Status"]
    if "ENTERED" in status_text:
        return "Position open"
    if recorded:
        return recorded
    if "QUALIFIED" in status_text:
        return "Qualified signal; entry not recorded"
    if "NIFTY FILTER" in status_text:
        return "NIFTY 500 filter does not support this direction"
    if "GAP UP" in status_text:
        return "Waiting for PDH breach and return above Today's Open"
    if "GAP DOWN" in status_text:
        return "Waiting for PDL breach and return below Today's Open"
    return "Open is inside PDH/PDL range"


board["Reason"] = board.apply(reason, axis=1)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Stocks", len(board))
c2.metric("Gap Up", int((board["GapType"] == "GAP_UP").sum()) if "GapType" in board.columns else 0)
c3.metric("Gap Down", int((board["GapType"] == "GAP_DOWN").sum()) if "GapType" in board.columns else 0)
c4.metric("Entered", len(position_symbols))
c5.metric("Qualified", len(approved_symbols - position_symbols))

st.caption(f"NIFTY 500: {market_change:+.2f}% • Entry window {ENTRY_START}–{ENTRY_END} IST • Updated {now.strftime('%H:%M:%S')} IST")

f1, f2, f3 = st.columns(3)
with f1:
    status_filter = st.selectbox("Status", ["ALL"] + sorted(board["Status"].dropna().unique().tolist()))
with f2:
    industry_values = sorted(board["Industry"].dropna().astype(str).unique().tolist()) if "Industry" in board.columns else []
    industry_filter = st.selectbox("Industry (information only)", ["ALL"] + industry_values)
with f3:
    search = st.text_input("Search stock", placeholder="e.g. RELIANCE")

view = board.copy()
if status_filter != "ALL":
    view = view[view["Status"] == status_filter]
if industry_filter != "ALL" and "Industry" in view.columns:
    view = view[view["Industry"].astype(str) == industry_filter]
if search.strip():
    q = search.strip().upper()
    view = view[view["Symbol"].astype(str).str.upper().str.contains(q, na=False)]

preferred = ["Status", "Symbol", "Industry", "TodayOpen", "PDH", "PDL", "Gap", "GapPercent", "NIFTY 500", "Reason"]
cols = [c for c in preferred if c in view.columns]
display = view[cols].copy()
for col in ["TodayOpen", "PDH", "PDL", "Gap"]:
    if col in display.columns:
        display[col] = display[col].map(money)
if "GapPercent" in display.columns:
    display["GapPercent"] = display["GapPercent"].map(pct)

st.subheader(f"📋 Stock-by-Stock Status ({len(display)} shown / {len(board)} total)")
st.dataframe(display, width="stretch", hide_index=True, height=620)

st.subheader("💰 Capital & Entry Status")
available_cash = state.get("available_cash") if isinstance(state, dict) else None
capital_items = [
    ("Configured Capital", money(250000)),
    ("Available Cash", money(available_cash) if available_cash is not None else "Not reported"),
    ("Open Positions", len(positions)),
    ("Max Positions", 2),
]
cap_cols = st.columns(len(capital_items))
for col, (label, value) in zip(cap_cols, capital_items):
    col.metric(label, value)

st.caption("Industry is displayed only for information/filtering. It is not a strategy condition. Rejection reasons come from recorded scanner/risk results when available; the dashboard does not invent a reason.")
render_daily_footer()
