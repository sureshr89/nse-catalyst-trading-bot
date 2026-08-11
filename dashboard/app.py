"""NSE Catalyst Trading Bot - robust Streamlit dashboard."""

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst Trading Bot",
    page_icon="📈",
    layout="wide",
)

# Keep the dashboard itself independent from optional bot/chart imports.
# A bot-side import/runtime problem must never prevent the web page from opening.
bot_error = None
start_bot = None
get_status = None

try:
    from bot_runner import start_bot as _start_bot, get_status as _get_status
    start_bot = _start_bot
    get_status = _get_status
except Exception as exc:
    bot_error = f"{type(exc).__name__}: {exc}"

if start_bot is not None:
    try:
        start_bot()
    except Exception as exc:
        bot_error = f"{type(exc).__name__}: {exc}"

if get_status is not None:
    try:
        bot_status = get_status() or {}
    except Exception as exc:
        bot_status = {}
        bot_error = f"{type(exc).__name__}: {exc}"
else:
    bot_status = {}

now = datetime.now(INDIA_TZ)

# Read settings only after the page has loaded successfully.
try:
    from config.settings import (
        TOTAL_CAPITAL,
        PAPER_TRADING,
        LIVE_TRADING,
        TRADING_START,
        LAST_ENTRY_TIME,
        SQUARE_OFF_TIME,
        SCAN_INTERVAL_SECONDS,
    )
except Exception:
    TOTAL_CAPITAL = 250000
    PAPER_TRADING = True
    LIVE_TRADING = False
    TRADING_START = "09:45"
    LAST_ENTRY_TIME = "13:30"
    SQUARE_OFF_TIME = "15:00"
    SCAN_INTERVAL_SECONDS = 5

status = str(bot_status.get("status", "WAITING"))
error_text = bot_status.get("error") or bot_error

st.title("📈 NSE Catalyst Trading Bot Dashboard")
st.caption("Dashboard build: 2026-08-11 runtime-fix-v3")

if error_text:
    st.error(f"Bot/runtime error: {error_text}")
elif status == "RUNNING":
    st.success("🟢 PAPER BOT RUNNING")
elif status == "ERROR":
    st.error("🔴 BOT ERROR")
else:
    st.warning("🟡 WAITING FOR MARKET SESSION")

s1, s2, s3, s4 = st.columns(4)
s1.metric("India Time", now.strftime("%H:%M:%S"))
s2.metric("Bot Status", status)
s3.metric("Last Bot Cycle", str(bot_status.get("last_cycle") or "—"))
s4.metric("Last Scanner Run", str(bot_status.get("last_scan") or "—"))

with st.expander("Bot / Strategy Status", expanded=True):
    a, b, c, d = st.columns(4)
    a.write(f"**Paper Trading:** {PAPER_TRADING}")
    b.write(f"**Live Trading:** {LIVE_TRADING}")
    c.write(f"**Scanner:** {bot_status.get('scanner_status', 'IDLE')}")
    d.write(f"**Scan Interval:** {SCAN_INTERVAL_SECONDS}s")
    st.write(
        f"**Entry:** {TRADING_START} → {LAST_ENTRY_TIME} IST | "
        f"**Square-off:** {SQUARE_OFF_TIME} IST | "
        f"**Capital:** ₹{TOTAL_CAPITAL:,.0f}"
    )

# Runtime metrics are deliberately read defensively.
def num(key, default=0.0):
    try:
        return float(bot_status.get(key, default) or default)
    except Exception:
        return float(default)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Available Capital", f"₹{num('available_capital', TOTAL_CAPITAL):,.2f}")
m2.metric("Used Capital", f"₹{num('used_capital'):,.2f}")
m3.metric("Open Positions", int(num("open_positions")))
m4.metric("Daily P&L", f"₹{num('daily_pnl'):,.2f}")

st.subheader("Trading Status")
st.write(f"**Message:** {bot_status.get('message', 'Dashboard is online.')}")
st.write(f"**Total Trades:** {int(num('total_trades'))}")
st.write(f"**Winning Trades:** {int(num('winning_trades'))}")
st.write(f"**Losing Trades:** {int(num('losing_trades'))}")
st.write(f"**Journal P&L:** ₹{num('journal_pnl'):,.2f}")

# Load CSVs only after the basic page is rendered; failures cannot break the app.
try:
    import pandas as pd
except Exception as exc:
    pd = None
    st.warning(f"Pandas unavailable: {type(exc).__name__}: {exc}")

if pd is not None:
    tab1, tab2 = st.tabs(["Trades", "Signals"])

    with tab1:
        try:
            trades_path = PROJECT_ROOT / "outputs" / "trades.csv"
            if trades_path.exists():
                trades = pd.read_csv(trades_path)
                st.dataframe(trades.tail(30).iloc[::-1], width="stretch")
            else:
                st.info("No completed trades yet.")
        except Exception as exc:
            st.warning(f"Could not load trades: {type(exc).__name__}: {exc}")

    with tab2:
        try:
            signals_path = PROJECT_ROOT / "outputs" / "signals.csv"
            if signals_path.exists():
                signals = pd.read_csv(signals_path)
                st.dataframe(signals.tail(50).iloc[::-1], width="stretch")
            else:
                st.info("No scanner signals recorded yet.")
        except Exception as exc:
            st.warning(f"Could not load signals: {type(exc).__name__}: {exc}")

st.sidebar.title("Trading Summary")
st.sidebar.write(f"**Bot:** {status}")
st.sidebar.write(f"**India Time:** {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"**Scanner:** {bot_status.get('scanner_status', 'IDLE')}")
st.sidebar.write(f"**Open Positions:** {int(num('open_positions'))}")
st.sidebar.write(f"**Daily P&L:** ₹{num('daily_pnl'):,.2f}")

# Auto-refresh without depending on streamlit-autorefresh.
st.markdown("<meta http-equiv='refresh' content='5'>", unsafe_allow_html=True)
