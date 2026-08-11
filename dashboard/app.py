"""
NSE Catalyst Trading Bot - non-blocking Streamlit dashboard.

The dashboard MUST render independently of the paper-trading worker.
The worker/watchdog is launched in a daemon background thread so a slow
Yahoo download, bot import, scanner, or trading dependency can never block
this Streamlit page from rendering.
"""
from datetime import datetime
from pathlib import Path
import json
import threading
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit_autorefresh import st_autorefresh

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"
INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst Trading Bot", page_icon="📈", layout="wide")

TOTAL_CAPITAL = 250000
PAPER_TRADING = True
LIVE_TRADING = False
TRADING_START = "09:45"
LAST_ENTRY_TIME = "13:30"
SQUARE_OFF_TIME = "15:00"
SCAN_INTERVAL_SECONDS = 30

try:
    from config.settings import (
        TOTAL_CAPITAL, PAPER_TRADING, LIVE_TRADING,
        TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME,
        SCAN_INTERVAL_SECONDS,
    )
except Exception:
    pass


# IMPORTANT: these objects live in the Streamlit Python process and are used
# only to launch the watchdog. We never wait for the worker on the UI thread.
_watchdog_lock = threading.Lock()
_watchdog_thread = None


def _launch_watchdog():
    global _watchdog_thread
    with _watchdog_lock:
        if _watchdog_thread is not None and _watchdog_thread.is_alive():
            return

        def target():
            global _watchdog_thread
            try:
                import bot_runner
                bot_runner.ensure_bot_running()
            except Exception as exc:
                try:
                    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    payload = read_status()
                    payload.update({
                        "status": "ERROR",
                        "message": "Dashboard is online, but the paper worker could not start.",
                        "worker_alive": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    with open(STATUS_FILE, "w", encoding="utf-8") as file:
                        json.dump(payload, file, indent=2, default=str)
                except Exception:
                    pass

        _watchdog_thread = threading.Thread(
            target=target,
            name="streamlit-paper-bot-watchdog",
            daemon=True,
        )
        _watchdog_thread.start()


def number(data, key, default=0.0):
    try:
        return float(data.get(key, default) or default)
    except Exception:
        return float(default)


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
            "last_scan_completed": None,
            "scan_duration_seconds": None,
            "last_signal_count": 0,
            "last_scan_error": None,
            "heartbeat": None,
            "worker_alive": False,
            "error": None,
            "open_positions": 0,
            "available_capital": TOTAL_CAPITAL,
            "used_capital": 0,
            "daily_pnl": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "journal_pnl": 0,
            "cycle_count": 0,
            "scan_count": 0,
        }


# Refresh the UI every 5 seconds. This does NOT run the trading work.
st_autorefresh(interval=5000, limit=None, key="nse_bot_dashboard_refresh")

# Render the page FIRST. Nothing below is allowed to block the Streamlit UI.
st.title("📈 NSE Catalyst Trading Bot Dashboard")
st.caption("Dashboard build: 2026-08-11 stable-v14")

now = datetime.now(INDIA_TZ)

# Start the watchdog asynchronously. The UI never waits for it.
_launch_watchdog()

bot_status = read_status()

# If the worker has not written a status yet, show a clean starting state.
status = str(bot_status.get("status", "STARTING"))
worker_alive = bool(bot_status.get("worker_alive", False))
scanner_status = str(bot_status.get("scanner_status", "IDLE"))

if bot_status.get("error") and status == "ERROR":
    st.error(f"Worker error: {bot_status['error']}")
elif status == "RUNNING" and worker_alive:
    st.success("🟢 PAPER BOT RUNNING")
elif status == "SCANNING" and worker_alive:
    st.success("🟢 PAPER BOT RUNNING — SCANNING")
elif status == "WAITING" and worker_alive:
    st.warning("🟡 WAITING FOR MARKET SESSION")
elif not worker_alive:
    st.warning("🟡 PAPER BOT WORKER STARTING/RETRYING — DASHBOARD IS ONLINE")
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
    c.write(f"Scanner: {scanner_status}")
    d.write(f"Scan Interval: {SCAN_INTERVAL_SECONDS}s")
    st.write(
        f"Entry: {TRADING_START} → {LAST_ENTRY_TIME} IST | "
        f"Square-off: {SQUARE_OFF_TIME} IST | Capital: ₹{TOTAL_CAPITAL:,.0f}"
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Available Capital", f"₹{number(bot_status, 'available_capital', TOTAL_CAPITAL):,.2f}")
m2.metric("Used Capital", f"₹{number(bot_status, 'used_capital'):,.2f}")
m3.metric("Open Positions", int(number(bot_status, "open_positions")))
m4.metric("Daily P&L", f"₹{number(bot_status, 'daily_pnl'):,.2f}")

st.subheader("Trading Status")
st.write(f"Message: {bot_status.get('message', 'Dashboard is online.')}")

x1, x2, x3, x4 = st.columns(4)
x1.metric("Total Trades", int(number(bot_status, "total_trades")))
x2.metric("Winning Trades", int(number(bot_status, "winning_trades")))
x3.metric("Losing Trades", int(number(bot_status, "losing_trades")))
x4.metric("Journal P&L", f"₹{number(bot_status, 'journal_pnl'):,.2f}")

st.subheader("Scanner Diagnostics")
q1, q2, q3, q4 = st.columns(4)
q1.metric("Scan Count", int(number(bot_status, "scan_count")))
q2.metric("Last Signals", int(number(bot_status, "last_signal_count")))
q3.metric("Last Scan Seconds", number(bot_status, "scan_duration_seconds"))
q4.metric("Worker Alive", "YES" if worker_alive else "NO")

if bot_status.get("last_scan_error"):
    st.error(f"Last scanner error: {bot_status['last_scan_error']}")

st.subheader("Worker Diagnostics")
d1, d2, d3, d4 = st.columns(4)
d1.write(f"Heartbeat: {bot_status.get('heartbeat') or '—'}")
d2.write(f"Cycles: {int(number(bot_status, 'cycle_count'))}")
d3.write(f"Last Scan: {bot_status.get('last_scan_completed') or '—'}")
d4.write(f"Worker: {'ALIVE' if worker_alive else 'STOPPED/STARTING'}")

if scanner_status == "SCANNING":
    st.info("Scanner is actively checking the market. No trade is taken until all strategy conditions are satisfied.")

st.sidebar.title("Trading Summary")
st.sidebar.write(f"Bot: {status}")
st.sidebar.write(f"India Time: {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"Scanner: {scanner_status}")
st.sidebar.write(f"Open Positions: {int(number(bot_status, 'open_positions'))}")
st.sidebar.write(f"Daily P&L: ₹{number(bot_status, 'daily_pnl'):,.2f}")
st.sidebar.write(f"Worker: {'ALIVE' if worker_alive else 'STARTING/STOPPED'}")
st.caption("Dashboard updates every 5 seconds without a browser/meta refresh.")
