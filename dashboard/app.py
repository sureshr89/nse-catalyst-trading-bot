"""
NSE Catalyst Trading Bot - SAFE Streamlit dashboard

The dashboard must always open even if the trading worker has an import,
market-data, or runtime problem. The paper bot is started AFTER the first
page render in a background timer, so a bot startup problem cannot prevent
the Streamlit page from loading.
"""

from datetime import datetime
from pathlib import Path
import json
import threading
from zoneinfo import ZoneInfo

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"
INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst Trading Bot",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# SETTINGS: use safe defaults so settings/import failures never kill the page.
# ---------------------------------------------------------------------------
TOTAL_CAPITAL = 250000
PAPER_TRADING = True
LIVE_TRADING = False
TRADING_START = "09:45"
LAST_ENTRY_TIME = "13:30"
SQUARE_OFF_TIME = "15:00"
SCAN_INTERVAL_SECONDS = 5

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
    pass


# ---------------------------------------------------------------------------
# Read status without importing the trading bot.
# ---------------------------------------------------------------------------
def read_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {
            "status": "STARTING",
            "message": "Dashboard is online. Paper bot is starting...",
            "scanner_status": "IDLE",
            "last_cycle": None,
            "last_scan": None,
            "error": None,
            "open_positions": 0,
            "available_capital": TOTAL_CAPITAL,
            "used_capital": 0,
            "daily_pnl": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "journal_pnl": 0,
        }


# ---------------------------------------------------------------------------
# Start bot only after Streamlit has rendered the page.
# ---------------------------------------------------------------------------
def _start_bot_later():
    try:
        from bot_runner import start_bot
        start_bot()
    except Exception as exc:
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATUS_FILE, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "status": "ERROR",
                        "message": "Dashboard is online, but paper bot failed to start.",
                        "scanner_status": "ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                        "last_cycle": None,
                        "last_scan": None,
                    },
                    file,
                    indent=2,
                )
        except Exception:
            pass


if "bot_start_scheduled" not in st.session_state:
    st.session_state.bot_start_scheduled = True
    threading.Timer(2.0, _start_bot_later).start()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
now = datetime.now(INDIA_TZ)
bot_status = read_status()
status = str(bot_status.get("status", "STARTING"))
error_text = bot_status.get("error")

st.title("📈 NSE Catalyst Trading Bot Dashboard")
st.caption("Dashboard build: 2026-08-11 runtime-fix-v5")

if error_text:
    st.error(f"Bot/runtime error: {error_text}")
elif status == "RUNNING":
    st.success("🟢 PAPER BOT RUNNING")
elif status == "WAITING":
    st.warning("🟡 WAITING FOR MARKET SESSION")
else:
    st.info("🔵 DASHBOARD ONLINE — STARTING PAPER BOT")

s1, s2, s3, s4 = st.columns(4)
s1.metric("India Time", now.strftime("%H:%M:%S"))
s2.metric("Bot Status", status)
s3.metric("Last Bot Cycle", str(bot_status.get("last_cycle") or "—"))
s4.metric("Last Scanner Run", str(bot_status.get("last_scan") or "—"))

with st.expander("Bot / Strategy Status", expanded=True):
    a, b, c, d = st.columns(4)
    a.write(f"Paper Trading: {PAPER_TRADING}")
    b.write(f"Live Trading: {LIVE_TRADING}")
    c.write(f"Scanner: {bot_status.get('scanner_status', 'IDLE')}")
    d.write(f"Scan Interval: {SCAN_INTERVAL_SECONDS}s")
    st.write(
        f"Entry: {TRADING_START} → {LAST_ENTRY_TIME} IST | "
        f"Square-off: {SQUARE_OFF_TIME} IST | "
        f"Capital: ₹{TOTAL_CAPITAL:,.0f}"
    )


def number(key, default=0.0):
    try:
        return float(bot_status.get(key, default) or default)
    except Exception:
        return float(default)


m1, m2, m3, m4 = st.columns(4)
m1.metric("Available Capital", f"₹{number('available_capital', TOTAL_CAPITAL):,.2f}")
m2.metric("Used Capital", f"₹{number('used_capital'):,.2f}")
m3.metric("Open Positions", int(number("open_positions")))
m4.metric("Daily P&L", f"₹{number('daily_pnl'):,.2f}")

st.subheader("Trading Status")
st.write(f"Message: {bot_status.get('message', 'Dashboard is online.')}")
st.write(f"Total Trades: {int(number('total_trades'))}")
st.write(f"Winning Trades: {int(number('winning_trades'))}")
st.write(f"Losing Trades: {int(number('losing_trades'))}")
st.write(f"Journal P&L: ₹{number('journal_pnl'):,.2f}")

if error_text:
    st.warning("The web dashboard is working. Only the paper-bot worker needs attention.")

st.sidebar.title("Trading Summary")
st.sidebar.write(f"Bot: {status}")
st.sidebar.write(f"India Time: {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"Scanner: {bot_status.get('scanner_status', 'IDLE')}")
st.sidebar.write(f"Open Positions: {int(number('open_positions'))}")
st.sidebar.write(f"Daily P&L: ₹{number('daily_pnl'):,.2f}")

# IMPORTANT: Do NOT use a browser meta-refresh here.
# The previous 5-second meta-refresh caused the whole browser page to reload
# repeatedly. The paper bot continues running independently in its background
# worker, so the dashboard remains stable until the user manually refreshes it.
