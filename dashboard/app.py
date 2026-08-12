"""NSE Catalyst Trading Bot - live Streamlit dashboard."""
from datetime import datetime
from pathlib import Path
import importlib.util
import json
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
SIGNALS_FILE = PROJECT_ROOT / "outputs" / "signals.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"
BOT_RUNNER_FILE = PROJECT_ROOT / "bot_runner.py"
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.py"
INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst Trading Bot", page_icon="📈", layout="wide")

TOTAL_CAPITAL = 250000
MAX_RISK_PER_TRADE = 1500
RISK_REWARD_RATIO = 1.5
MAX_OPEN_POSITIONS = 2
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
    MAX_RISK_PER_TRADE = float(settings.MAX_RISK_PER_TRADE)
    RISK_REWARD_RATIO = float(settings.RISK_REWARD_RATIO)
    MAX_OPEN_POSITIONS = int(settings.MAX_OPEN_POSITIONS)
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


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            value = json.load(file)
        return value
    except Exception:
        return default


def read_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def read_status():
    status = read_json(STATUS_FILE, {})
    if status:
        return status
    return {
        "status": "STARTING",
        "message": "Dashboard is online. Paper bot is starting...",
        "scanner_status": "IDLE",
        "worker_alive": False,
        "last_cycle": None,
        "last_scan": None,
        "last_scan_completed": None,
        "scan_duration_seconds": None,
        "last_signal_count": 0,
        "last_scan_error": None,
        "heartbeat": None,
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
        "worker_id": None,
        "trading_start": TRADING_START,
        "last_entry_time": LAST_ENTRY_TIME,
        "square_off_time": SQUARE_OFF_TIME,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
    }


def heartbeat_is_fresh(heartbeat, max_age_seconds=90):
    if not heartbeat:
        return False
    try:
        value = datetime.fromisoformat(str(heartbeat))
        if value.tzinfo is None:
            value = value.replace(tzinfo=INDIA_TZ)
        age = (datetime.now(INDIA_TZ) - value).total_seconds()
        return 0 <= age <= max_age_seconds
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def get_persistent_worker():
    if not BOT_RUNNER_FILE.exists():
        raise FileNotFoundError(f"Missing worker file: {BOT_RUNNER_FILE}")
    module_name = "nse_paper_bot_runner_persistent_v30"
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
st.caption(
    f"NIFTY 100 Gap-Failure + Open-Reclaim | Paper only | "
    f"Entry {TRADING_START}–{LAST_ENTRY_TIME} IST | Square-off {SQUARE_OFF_TIME} IST"
)

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
            local_alive = bool(live_status.get("worker_alive", False))
            bot_status.update(live_status)
            if not local_alive:
                disk_status = read_status()
                if heartbeat_is_fresh(disk_status.get("heartbeat")):
                    bot_status["worker_alive"] = True
                    bot_status["worker_id"] = disk_status.get("worker_id") or bot_status.get("worker_id")
                    bot_status["heartbeat"] = disk_status.get("heartbeat")
                    bot_status["status"] = disk_status.get("status", bot_status.get("status", "WAITING"))
    except Exception as exc:
        st.warning(f"Could not read live worker status: {type(exc).__name__}: {exc}")

status = str(bot_status.get("status", "STARTING"))
worker_alive = bool(bot_status.get("worker_alive", False))
scanner_status = str(bot_status.get("scanner_status", "IDLE"))

if bot_status.get("error") and status == "ERROR":
    st.error(f"Worker error: {bot_status['error']}")
elif status in {"RUNNING", "SCANNING"} and worker_alive:
    st.success("🟢 PAPER BOT RUNNING")
elif status == "WAITING" and worker_alive:
    st.warning("🟡 WAITING FOR MARKET SESSION")
elif not worker_alive:
    st.warning("🟡 PAPER BOT WORKER STARTING/RETRYING")
else:
    st.info("🔵 DASHBOARD ONLINE — STARTING PAPER BOT")

# -----------------------------------------------------------------------------
# LIVE BOT STATUS
# -----------------------------------------------------------------------------
s1, s2, s3, s4 = st.columns(4)
s1.metric("India Time", now.strftime("%H:%M:%S"))
s2.metric("Bot Status", status)
s3.metric("Last Bot Cycle", str(bot_status.get("last_cycle") or "—"))
s4.metric("Last Scanner Run", str(bot_status.get("last_scan") or "—"))

with st.expander("Bot / Strategy Configuration", expanded=True):
    a, b, c, d, e = st.columns(5)
    a.write(f"Universe: **NIFTY 100**")
    b.write(f"Risk/Trade: **₹{MAX_RISK_PER_TRADE:,.0f}**")
    c.write(f"R:R: **1:{RISK_REWARD_RATIO:g}**")
    d.write(f"Max Positions: **{MAX_OPEN_POSITIONS}**")
    e.write(f"Scan: **{SCAN_INTERVAL_SECONDS}s**")
    st.write(
        f"Strategy: **GAP_FAILURE_OPEN_RECLAIM** | "
        f"Entry: **{TRADING_START}–{LAST_ENTRY_TIME} IST** | "
        f"Mandatory square-off: **{SQUARE_OFF_TIME} IST**"
    )
    st.write(
        f"Paper Trading: **{PAPER_TRADING}** | Live Trading: **{LIVE_TRADING}** | "
        f"Capital: **₹{TOTAL_CAPITAL:,.0f}**"
    )

# -----------------------------------------------------------------------------
# CAPITAL / POSITION STATUS
# -----------------------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Available Capital", f"₹{number(bot_status, 'available_capital', TOTAL_CAPITAL):,.2f}")
m2.metric("Used Capital", f"₹{number(bot_status, 'used_capital'):,.2f}")
m3.metric("Open Positions", int(number(bot_status, "open_positions")))
m4.metric("Daily P&L", f"₹{number(bot_status, 'daily_pnl'):,.2f}")

st.subheader("Trading Status")
st.write(f"Message: {bot_status.get('message', 'Dashboard is online.')}")

x1, x2, x3, x4 = st.columns(4)
x1.metric("Closed Trades", int(number(bot_status, "total_trades")))
x2.metric("Winning Trades", int(number(bot_status, "winning_trades")))
x3.metric("Losing Trades", int(number(bot_status, "losing_trades")))
x4.metric("Journal P&L", f"₹{number(bot_status, 'journal_pnl'):,.2f}")

# -----------------------------------------------------------------------------
# OPEN POSITIONS - directly from durable paper-engine state
# -----------------------------------------------------------------------------
state = read_json(STATE_FILE, {})
open_positions = state.get("open_positions", {}) or {}

st.subheader("📌 Open Positions")
if open_positions:
    rows = []
    for symbol, position in open_positions.items():
        entry = float(position.get("entry", 0) or 0)
        stop = float(position.get("stop_loss", 0) or 0)
        target = float(position.get("target", 0) or 0)
        qty = int(float(position.get("quantity", 0) or 0))
        rows.append({
            "Symbol": symbol,
            "Side": position.get("signal", ""),
            "Entry": entry,
            "Stop Loss": stop,
            "Target": target,
            "Qty": qty,
            "Risk": round(abs(entry - stop) * qty, 2),
            "R:R": position.get("risk_reward", RISK_REWARD_RATIO),
            "Entry Time": position.get("entry_time", ""),
            "Setup": position.get("setup_type", "GAP_FAILURE_OPEN_RECLAIM"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions.")

# -----------------------------------------------------------------------------
# SCANNER DIAGNOSTICS
# -----------------------------------------------------------------------------
st.subheader("🔎 Scanner Diagnostics")
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
d3.write(f"Last Scan Completed: {bot_status.get('last_scan_completed') or '—'}")
d4.write(f"Worker: {'ALIVE' if worker_alive else 'STOPPED/STARTING'}")

# -----------------------------------------------------------------------------
# RECENT SIGNALS - this is the missing execution/decision log view
# -----------------------------------------------------------------------------
signals = read_csv(SIGNALS_FILE)
st.subheader("📡 Recent Scanner Signals")
if signals.empty:
    st.info("No scanner signals have been recorded yet.")
else:
    recent = signals.tail(20).copy()
    preferred = [
        "timestamp", "symbol", "signal", "entry", "stop_loss", "target",
        "risk_reward", "pdc", "today_open", "today_low", "today_high",
        "nifty100_direction", "sector", "sector_direction", "stock_today_direction",
        "setup_type", "approved", "reason",
    ]
    columns = [c for c in preferred if c in recent.columns]
    st.dataframe(recent[columns].iloc[::-1], use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# RECENT TRADES - actual journal rows
# -----------------------------------------------------------------------------
trades = read_csv(TRADES_FILE)
st.subheader("📒 Recent Trade Log")
if trades.empty:
    st.info("No trade journal entries yet.")
else:
    recent_trades = trades.tail(20).copy()
    preferred = [
        "trade_id", "symbol", "signal", "entry_time", "entry", "stop_loss", "target",
        "quantity", "exit_time", "exit_price", "exit_reason", "risk", "reward", "rr",
        "pnl", "actual_risk", "position_value", "pdc", "today_open", "today_low", "today_high",
        "nifty100_direction", "sector", "sector_direction", "stock_today_direction",
        "setup_type", "status",
    ]
    columns = [c for c in preferred if c in recent_trades.columns]
    st.dataframe(recent_trades[columns].iloc[::-1], use_container_width=True, hide_index=True)

st.sidebar.title("Trading Summary")
st.sidebar.write(f"Bot: {status}")
st.sidebar.write(f"India Time: {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"Scanner: {scanner_status}")
st.sidebar.write(f"Open Positions: {int(number(bot_status, 'open_positions'))}")
st.sidebar.write(f"Daily P&L: ₹{number(bot_status, 'daily_pnl'):,.2f}")
st.sidebar.write(f"Worker: {'ALIVE' if worker_alive else 'STARTING/STOPPED'}")
st.sidebar.write(f"Dashboard Refresh: {now.strftime('%H:%M:%S IST')}")
st.sidebar.divider()
st.sidebar.page_link("pages/analysis.py", label="📊 Analysis", icon="📊")
