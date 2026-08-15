from pathlib import Path
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running

ROOT = Path(__file__).resolve().parent.parent
INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START = "09:45"
ENTRY_END = "14:00"
NIFTY_THRESHOLD = 0.25

st.set_page_config(
    page_title="NSE Catalyst | NIFTY 500 Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st_autorefresh(interval=5000, key="live")
st.markdown(load_css(), unsafe_allow_html=True)


def load_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def grid(items):
    st.markdown(
        '<div class="metric-grid">'
        + "".join(
            f'<div class="metric-card"><small>{label}</small><b>{value}</b></div>'
            for label, value in items
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def heartbeat_alive(value, max_age_seconds=90):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max_age_seconds
    except Exception:
        return False


render_nav()
status = load_json(ROOT / "outputs/bot_status.json")
state = load_json(ROOT / "outputs/paper_engine_state.json")
diag = load_json(ROOT / "outputs/scanner_diagnostics.json")
signals = load_csv(ROOT / "outputs/signals.csv")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

try:
    live = ensure_bot_running()
    if isinstance(live, dict):
        status.update(live)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

now = datetime.now(INDIA_TZ)
worker = bool(status.get("worker_alive", False)) and heartbeat_alive(status.get("heartbeat"))
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

clock = now.strftime("%H:%M")
if clock < ENTRY_START:
    window = "🕘 PREPARE"
elif clock <= ENTRY_END:
    window = "🟢 ACTIVE"
else:
    window = "🔒 CLOSED"

st.title("📈 NIFTY 500 Trading Bot")
st.caption("Live command center • PDH/PDL → Today's Open → 1-minute reversal • Paper trading only")

if worker:
    st.success("🟢 BOT RUNNING • PAPER TRADING")
else:
    st.warning("🟠 BOT WORKER NOT CONFIRMED ALIVE")

# Main decision strip — same shared metric-card style, but focused on today's decision.
st.subheader("LIVE MARKET DECISION")
grid([
    ("NIFTY 500", f"{market_change:+.2f}%"),
    ("Permission", permission),
    ("Entry Window", window),
    ("Open Positions", len(positions)),
    ("India Time", now.strftime("%H:%M:%S")),
])
st.caption(f"{permission_note} • Entries {ENTRY_START}–{ENTRY_END} IST")

if status.get("error"):
    st.error(str(status["error"]))

# The main page now explains the new strategy as a decision flow instead of exposing scanner internals.
st.subheader("🎯 TODAY'S TRADE LOGIC")
c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("### 🟢 BUY")
    grid([
        ("1. Market", "NIFTY 500 ≥ +0.25%"),
        ("2. Opening", "Today's Open > PDH"),
        ("3. Reaction", "Price closes below PDH"),
        ("4. Trigger", "1m Open < Today's Open"),
        ("5. Confirmation", "1m Close > Today's Open"),
    ])
with c2:
    st.markdown("### 🔴 SELL")
    grid([
        ("1. Market", "NIFTY 500 ≤ −0.25%"),
        ("2. Opening", "Today's Open < PDL"),
        ("3. Reaction", "Price closes above PDL"),
        ("4. Trigger", "1m Open > Today's Open"),
        ("5. Confirmation", "1m Close < Today's Open"),
    ])

st.caption("Sector/Industry and stock direction must also agree with the trade. Only completed 1-minute data is used; no look-ahead.")

st.subheader("🧭 RISK & EXECUTION")
grid([
    ("Universe", "NIFTY 500"),
    ("Entry", "Completed 1-minute reversal"),
    ("BUY Stop", "PDH"),
    ("SELL Stop", "PDL"),
    ("R:R", "1 : 1.25"),
    ("Risk / Trade", "₹1,400–₹1,500"),
    ("Max Positions", "2"),
    ("Daily Max Loss", "₹3,750"),
    ("Square-off", "15:00 IST"),
    ("Trading Mode", "PAPER"),
])

st.subheader("📡 LIVE SIGNALS")
if not signals.empty:
    display = signals.copy()
    preferred = [
        "symbol", "signal", "entry_time", "entry", "stop_loss", "target",
        "nifty500_change_pct", "stock_direction", "industry_direction",
    ]
    cols = [c for c in preferred if c in display.columns]
    if cols:
        display = display[cols].tail(20).iloc[::-1]
    st.dataframe(display, width="stretch", hide_index=True, height=300)
else:
    st.info("No qualifying signal yet. The bot will show a row here when every strategy condition is satisfied.")

if positions:
    st.subheader("📍 OPEN POSITIONS")
    rows = []
    for symbol, position in positions.items():
        rows.append({
            "Stock": symbol,
            "Side": str(position.get("signal", "")).upper(),
            "Entry": position.get("entry", "—"),
            "SL": position.get("stop_loss", "—"),
            "Target": position.get("target", "—"),
            "Qty": position.get("quantity", "—"),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

st.caption(
    f"Completed 1-minute scanner coverage: {float(diag.get('market_data_coverage', 0) or 0) * 100:.1f}% • "
    f"Final signals: {diag.get('final_signals', 0) if isinstance(diag, dict) else 0} • Auto-refresh: 5 seconds"
)
render_daily_footer()
