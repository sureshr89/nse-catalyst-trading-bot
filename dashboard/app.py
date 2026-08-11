"""
NSE Catalyst Trading Bot - SAFE Streamlit dashboard

The dashboard must always render first. The paper worker is started
asynchronously after the visible dashboard has been rendered so a worker
startup/import problem can never prevent the page from opening.
"""

from datetime import datetime
from pathlib import Path
import json
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

TOTAL_CAPITAL = 250000
PAPER_TRADING = True
LIVE_TRADING = False
TRADING_START = "09:45"
LAST_ENTRY_TIME = "13:30"
SQUARE_OFF_TIME = "15:00"
SCAN_INTERVAL_SECONDS = 30

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
    # Keep the dashboard usable even if config has a deployment problem.
    pass


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


def number(data, key, default=0.0):
    try:
        return float(data.get(key, default) or default)
    except Exception:
        return float(default)


def ensure_worker():
    """Start/watch the paper worker with backward compatibility."""
    try:
        import bot_runner
    except Exception as exc:
        raise RuntimeError(
            f"Cannot import bot_runner: {type(exc).__name__}: {exc}"
        ) from exc

    watchdog = getattr(bot_runner, "ensure_bot_running", None)
    if callable(watchdog):
        return watchdog()

    starter = getattr(bot_runner, "start_bot", None)
    if callable(starter):
        return starter()

    raise RuntimeError(
        "bot_runner.py has neither ensure_bot_running() nor start_bot()."
    )


st.title("📈 NSE Catalyst Trading Bot Dashboard")
st.caption("Dashboard build: 2026-08-11 stable-v10")


@st.fragment(run_every="5s")
def live_dashboard():
    """Refresh only dashboard data; do not reload the browser page."""

    now = datetime.now(INDIA_TZ)
    bot_status = read_status()
    status = str(bot_status.get("status", "STARTING"))
    error_text = bot_status.get("error")
    worker_alive = bool(bot_status.get("worker_alive", False))
    scanner_status = str(bot_status.get("scanner_status", "IDLE"))

    if error_text and status not in {"STOPPED", "ERROR"}:
        st.warning(f"Last worker message: {error_text}")

    if status == "RUNNING" and worker_alive:
        st.success("🟢 PAPER BOT RUNNING")
    elif status == "SCANNING" or scanner_status == "SCANNING":
        st.success("🟢 PAPER BOT RUNNING — SCANNING")
    elif status == "WAITING" and worker_alive:
        st.warning("🟡 WAITING FOR MARKET SESSION")
    elif status in {"STOPPED", "ERROR"}:
        st.error("🔴 PAPER BOT WORKER NEEDS RESTART — WATCHDOG ACTIVE")
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
            f"Square-off: {SQUARE_OFF_TIME} IST | "
            f"Capital: ₹{TOTAL_CAPITAL:,.0f}"
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

    scan_error = bot_status.get("last_scan_error")
    if scan_error:
        st.error(f"Last scanner error: {scan_error}")

    st.subheader("Worker Diagnostics")
    d1, d2, d3, d4 = st.columns(4)
    d1.write(f"Heartbeat: {bot_status.get('heartbeat') or '—'}")
    d2.write(f"Cycles: {int(number(bot_status, 'cycle_count'))}")
    d3.write(f"Last Scan: {bot_status.get('last_scan_completed') or '—'}")
    d4.write(f"Worker: {'ALIVE' if worker_alive else 'STOPPED'}")

    if scanner_status == "SCANNING":
        st.info("Scanner is actively checking the market. No trade is taken until all strategy conditions are satisfied.")

    # IMPORTANT: start/watch the worker only AFTER the dashboard has rendered.
    # A bot import/start failure therefore cannot blank the Streamlit page.
    try:
        ensure_worker()
    except Exception as exc:
        st.error(f"Worker watchdog error: {type(exc).__name__}: {exc}")


live_dashboard()

st.sidebar.title("Trading Summary")
initial = read_status()
st.sidebar.write(f"Bot: {initial.get('status', 'STARTING')}")
st.sidebar.write(f"India Time: {datetime.now(INDIA_TZ).strftime('%H:%M:%S IST')}")
st.sidebar.write(f"Scanner: {initial.get('scanner_status', 'IDLE')}")
st.sidebar.write(f"Open Positions: {int(number(initial, 'open_positions'))}")
st.sidebar.write(f"Daily P&L: ₹{number(initial, 'daily_pnl'):,.2f}")

st.caption("Live status refreshes inside the page; the browser itself is not meta-refreshed.")
