"""NSE Catalyst Trading Bot - stable Streamlit dashboard."""
from datetime import datetime
from pathlib import Path
import importlib.util
import json
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit_autorefresh import st_autorefresh

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"
BOT_RUNNER_FILE = PROJECT_ROOT / "bot_runner.py"
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.py"
INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst Trading Bot", page_icon="📈", layout="wide")

TOTAL_CAPITAL = 250000
PAPER_TRADING = True
LIVE_TRADING = False
TRADING_START = "09:45"
LAST_ENTRY_TIME = "14:00"
SQUARE_OFF_TIME = "15:00"
SCAN_INTERVAL_SECONDS = 30
SETTINGS_LOAD_ERROR = None

try:
    spec = importlib.util.spec_from_file_location("nse_current_settings", SETTINGS_FILE)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load config/settings.py")
    settings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(settings)
    TOTAL_CAPITAL = int(settings.TOTAL_CAPITAL)
    PAPER_TRADING = bool(settings.PAPER_TRADING)
    LIVE_TRADING = bool(settings.LIVE_TRADING)
    TRADING_START = str(settings.TRADING_START)
    LAST_ENTRY_TIME = str(settings.LAST_ENTRY_TIME)
    SQUARE_OFF_TIME = str(settings.SQUARE_OFF_TIME)
    SCAN_INTERVAL_SECONDS = int(settings.SCAN_INTERVAL_SECONDS)
except Exception as exc:
    SETTINGS_LOAD_ERROR = f"{type(exc).__name__}: {exc}"


def number(data, key, default=0.0):
    try:
        return float(data.get(key, default) or default)
    except Exception:
        return float(default)


def read_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "status": "STARTING", "message": "Dashboard is online. Paper bot is starting...",
            "scanner_status": "IDLE", "worker_alive": False,
            "last_cycle": None, "last_scan": None, "last_scan_completed": None,
            "scan_duration_seconds": None, "last_signal_count": 0,
            "last_scan_error": None, "heartbeat": None, "error": None,
            "open_positions": 0, "available_capital": TOTAL_CAPITAL,
            "used_capital": 0, "daily_pnl": 0, "total_trades": 0,
            "winning_trades": 0, "losing_trades": 0, "journal_pnl": 0,
            "cycle_count": 0, "scan_count": 0, "worker_id": None,
            "trading_start": TRADING_START, "last_entry_time": LAST_ENTRY_TIME,
            "square_off_time": SQUARE_OFF_TIME,
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        }


@st.cache_resource(show_spinner=False)
def get_persistent_worker():
    """Load bot_runner once per Streamlit server process."""
    if not BOT_RUNNER_FILE.exists():
        raise FileNotFoundError(f"Missing worker file: {BOT_RUNNER_FILE}")

    module_name = "nse_paper_bot_runner_persistent_v22"
    spec = importlib.util.spec_from_file_location(module_name, BOT_RUNNER_FILE)
    if spec is None or spec.loader is None:
        raise ImportError("Could not create a loader for bot_runner.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    starter = getattr(module, "ensure_bot_running", None)
    if not callable(starter):
        raise RuntimeError("Current bot_runner.py does not provide ensure_bot_running().")

    starter()
    return module


st_autorefresh(interval=5000, limit=None, key="nse_bot_dashboard_refresh")
now = datetime.now(INDIA_TZ)

st.title("📈 NSE Catalyst Trading Bot Dashboard")
st.caption("Dashboard build: 2026-08-11 stable-v22 — config-authoritative + single-worker + atomic status")

if SETTINGS_LOAD_ERROR:
    st.error(f"Settings load error: {SETTINGS_LOAD_ERROR}")

try:
    worker_module = get_persistent_worker()
    try:
        worker_module.ensure_bot_running()
    except Exception as exc:
        st.error(f"Worker watchdog error: {type(exc).__name__}: {exc}")
except Exception as exc:
    worker_module = None
    st.error(f"Paper worker could not start: {type(exc).__name__}: {exc}")

bot_status = read_status()
if worker_module is not None:
    try:
        live_status = worker_module.get_status()
        if isinstance(live_status, dict):
            bot_status.update(live_status)
    except Exception as exc:
        st.warning(f"Could not read live worker status: {type(exc).__name__}: {exc}")

status = str(bot_status.get("status", "STARTING"))
worker_alive = bool(bot_status.get("worker_alive", False))
scanner_status = str(bot_status.get("scanner_status", "IDLE"))

# settings.py is authoritative. Old bot_status.json values must not overwrite it.
effective_start = TRADING_START
effective_entry = LAST_ENTRY_TIME
effective_square = SQUARE_OFF_TIME
effective_scan = SCAN_INTERVAL_SECONDS

if bot_status.get("error") and status == "ERROR":
    st.error(f"Worker error: {bot_status['error']}")
elif status in {"RUNNING", "SCANNING"} and worker_alive:
    st.success("🟢 PAPER BOT RUNNING")
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
    d.write(f"Scan Interval: {effective_scan}s")
    st.write(
        f"Effective config: Entry {effective_start} → {effective_entry} IST | "
        f"Square-off: {effective_square} IST | Capital: ₹{TOTAL_CAPITAL:,.0f}"
    )
    st.write("Configuration source: config/settings.py")
    st.write(f"Worker ID: {bot_status.get('worker_id') or '—'}")

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

st.sidebar.title("Trading Summary")
st.sidebar.write(f"Bot: {status}")
st.sidebar.write(f"India Time: {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"Scanner: {scanner_status}")
st.sidebar.write(f"Open Positions: {int(number(bot_status, 'open_positions'))}")
st.sidebar.write(f"Daily P&L: ₹{number(bot_status, 'daily_pnl'):,.2f}")
st.sidebar.write(f"Worker: {'ALIVE' if worker_alive else 'STARTING/STOPPED'}")
st.sidebar.write(f"Dashboard Refresh: {now.strftime('%H:%M:%S IST')}")
