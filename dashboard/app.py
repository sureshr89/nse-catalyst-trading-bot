"""NSE Catalyst Trading Bot - clean live operations dashboard."""
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

st.set_page_config(page_title="NSE Catalyst | Live", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=5000, limit=None, key="nse_live_refresh")

# Minimal visual system: the live page is an operations screen, not a research page.
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}
[data-testid="stMetric"] {padding: .65rem .8rem; border: 1px solid rgba(128,128,128,.18); border-radius: 10px;}
.live-title {font-size: 2rem; font-weight: 700; margin-bottom: .1rem;}
.live-subtitle {opacity: .72; margin-bottom: 1.2rem;}
.section-title {font-size: 1.05rem; font-weight: 650; margin-top: 1.2rem; margin-bottom: .55rem;}
.status-pill {display:inline-block; padding:.3rem .65rem; border-radius:999px; font-weight:650; border:1px solid rgba(128,128,128,.2);}
</style>
""", unsafe_allow_html=True)

TOTAL_CAPITAL = 250000
MAX_RISK_PER_TRADE = 1500
MIN_REQUIRED_RISK = 1400
RISK_REWARD_RATIO = 1.25
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
    MIN_REQUIRED_RISK = float(settings.MIN_REQUIRED_RISK)
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


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {} if default is None else default


def read_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def number(data, key, default=0.0):
    try:
        return float(data.get(key, default) or default)
    except Exception:
        return float(default)


def heartbeat_is_fresh(value, max_age_seconds=90):
    if not value:
        return False
    try:
        stamp = datetime.fromisoformat(str(value))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        age = (datetime.now(INDIA_TZ) - stamp).total_seconds()
        return 0 <= age <= max_age_seconds
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def load_worker():
    if not BOT_RUNNER_FILE.exists():
        raise FileNotFoundError(f"Missing worker file: {BOT_RUNNER_FILE}")
    spec = importlib.util.spec_from_file_location("nse_paper_bot_runner_persistent_v30", BOT_RUNNER_FILE)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load bot_runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    starter = getattr(module, "ensure_bot_running", None)
    if not callable(starter):
        raise RuntimeError("bot_runner.py does not provide ensure_bot_running().")
    starter()
    return module


def fmt_money(value):
    return f"₹{float(value or 0):,.2f}"


def fmt_time(value):
    if not value:
        return "—"
    text = str(value).replace("T", " ")
    return text[:19]


now = datetime.now(INDIA_TZ)
worker_module = None
worker_error = None
try:
    worker_module = load_worker()
except Exception as exc:
    worker_error = f"{type(exc).__name__}: {exc}"

bot_status = read_json(STATUS_FILE, {})
if worker_module is not None:
    try:
        live_status = worker_module.get_status()
        if isinstance(live_status, dict):
            bot_status.update(live_status)
    except Exception as exc:
        bot_status["status_read_error"] = f"{type(exc).__name__}: {exc}"

worker_alive = bool(bot_status.get("worker_alive", False)) or heartbeat_is_fresh(bot_status.get("heartbeat"))
status = str(bot_status.get("status", "STARTING")).upper()
scanner_status = str(bot_status.get("scanner_status", "IDLE")).upper()
state = read_json(STATE_FILE, {})
open_positions = state.get("open_positions", {}) or {}
trades = read_csv(TRADES_FILE)
signals = read_csv(SIGNALS_FILE)

# ------------------------------- SIDEBAR -------------------------------
st.sidebar.markdown("## NSE Catalyst")
st.sidebar.caption("Live paper-trading operations")
st.sidebar.divider()
st.sidebar.metric("Bot", status)
st.sidebar.metric("Worker", "ALIVE" if worker_alive else "OFFLINE")
st.sidebar.metric("Positions", f"{len(open_positions)} / {MAX_OPEN_POSITIONS}")
st.sidebar.metric("Daily P&L", fmt_money(number(bot_status, "daily_pnl")))
st.sidebar.divider()
st.sidebar.page_link("pages/analysis.py", label="📊 Strategy Analysis")
st.sidebar.caption(f"Auto refresh: 5 seconds • {now.strftime('%H:%M:%S IST')}")

# ------------------------------- HEADER --------------------------------
st.markdown('<div class="live-title">📈 NSE Catalyst Trading Bot</div>', unsafe_allow_html=True)
st.markdown(f'<div class="live-subtitle">NIFTY 100 • Gap-Failure + Open-Reclaim • Paper Trading • {TRADING_START}–{LAST_ENTRY_TIME} IST • Square-off {SQUARE_OFF_TIME} IST</div>', unsafe_allow_html=True)

if worker_error:
    st.error(f"Worker unavailable: {worker_error}")
elif status == "ERROR":
    st.error(f"BOT ERROR — {bot_status.get('error') or bot_status.get('message') or 'Unknown worker error'}")
elif status in {"RUNNING", "SCANNING"} and worker_alive:
    st.success("🟢 BOT RUNNING • PAPER TRADING")
elif status == "WAITING" and worker_alive:
    st.warning("🟡 BOT READY • WAITING FOR MARKET SESSION")
elif worker_alive:
    st.info("🔵 WORKER ALIVE • STATUS INITIALIZING")
else:
    st.warning("🟠 WORKER NOT CONFIRMED ALIVE")

# ----------------------------- LIVE STATUS -----------------------------
st.markdown('<div class="section-title">Live Status</div>', unsafe_allow_html=True)
a, b, c, d, e, f = st.columns(6)
a.metric("India Time", now.strftime("%H:%M:%S"))
b.metric("Bot", status)
c.metric("Worker", "ALIVE" if worker_alive else "OFFLINE")
d.metric("Scanner", scanner_status)
e.metric("Open Positions", len(open_positions))
f.metric("Daily P&L", fmt_money(number(bot_status, "daily_pnl")))

# ------------------------------ CAPITAL --------------------------------
st.markdown('<div class="section-title">Capital & Risk</div>', unsafe_allow_html=True)
a, b, c, d, e = st.columns(5)
a.metric("Starting Capital", fmt_money(TOTAL_CAPITAL))
b.metric("Available", fmt_money(number(bot_status, "available_capital", TOTAL_CAPITAL)))
c.metric("Used", fmt_money(number(bot_status, "used_capital")))
d.metric("Risk / Trade", f"₹{MIN_REQUIRED_RISK:,.0f}–₹{MAX_RISK_PER_TRADE:,.0f}")
e.metric("R:R", f"1:{RISK_REWARD_RATIO:g}")

# --------------------------- OPEN POSITIONS ----------------------------
st.markdown('<div class="section-title">Open Positions</div>', unsafe_allow_html=True)
if open_positions:
    rows = []
    for symbol, position in open_positions.items():
        entry = float(position.get("entry", 0) or 0)
        stop = float(position.get("stop_loss", 0) or 0)
        target = float(position.get("target", 0) or 0)
        qty = int(float(position.get("quantity", 0) or 0))
        rows.append({
            "Stock": symbol,
            "Side": str(position.get("signal", "")).upper(),
            "Entry": entry,
            "Stop Loss": stop,
            "Target": target,
            "Qty": qty,
            "Risk": round(abs(entry - stop) * qty, 2),
            "R:R": position.get("risk_reward", RISK_REWARD_RATIO),
            "Entry Time": fmt_time(position.get("entry_time")),
            "Setup": position.get("setup_type", "GAP_FAILURE_OPEN_RECLAIM"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions.")

# ---------------------------- TRADE SUMMARY ---------------------------
closed = trades.copy()
if not closed.empty and "status" in closed.columns:
    closed = closed[closed["status"].astype(str).str.upper() == "CLOSED"].copy()
if not closed.empty and "pnl" in closed.columns:
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0)
wins = int((closed["pnl"] > 0).sum()) if not closed.empty else 0
losses = int((closed["pnl"] < 0).sum()) if not closed.empty else 0

st.markdown('<div class="section-title">Today's Trading</div>', unsafe_allow_html=True)
a, b, c, d, e = st.columns(5)
a.metric("Closed Trades", len(closed))
b.metric("Wins", wins)
c.metric("Losses", losses)
d.metric("Win Rate", f"{wins / len(closed) * 100:.1f}%" if len(closed) else "0.0%")
e.metric("Journal P&L", fmt_money(number(bot_status, "journal_pnl")))

if not closed.empty:
    preferred = ["trade_id", "symbol", "signal", "entry_time", "entry", "exit_time", "exit_price", "exit_reason", "quantity", "risk", "reward", "rr", "pnl", "status"]
    cols = [c for c in preferred if c in closed.columns]
    st.dataframe(closed[cols].iloc[::-1].head(20), use_container_width=True, hide_index=True)
else:
    st.info("No closed trades recorded yet.")

# ---------------------------- SCANNER ---------------------------------
st.markdown('<div class="section-title">Scanner Activity</div>', unsafe_allow_html=True)
a, b, c, d, e = st.columns(5)
a.metric("Total Scans", int(number(bot_status, "scan_count")))
b.metric("Last Signals", int(number(bot_status, "last_signal_count")))
c.metric("Last Scan", fmt_time(bot_status.get("last_scan")))
d.metric("Scan Duration", f'{number(bot_status, "scan_duration_seconds"):.2f}s')
e.metric("Cycle Count", int(number(bot_status, "cycle_count")))
if bot_status.get("last_scan_error"):
    st.error(f"Last scanner error: {bot_status['last_scan_error']}")

if not signals.empty:
    preferred = ["timestamp", "symbol", "signal", "entry", "stop_loss", "target", "risk_reward", "actual_risk", "pdc", "today_open", "nifty100_direction", "sector", "sector_direction", "stock_today_direction", "previous_day_direction", "setup_type", "approved", "reason"]
    cols = [c for c in preferred if c in signals.columns]
    st.dataframe(signals[cols].iloc[::-1].head(20), use_container_width=True, hide_index=True)
else:
    st.info("No scanner signals recorded yet.")

# --------------------------- DIAGNOSTICS ------------------------------
with st.expander("System Diagnostics", expanded=False):
    a, b, c, d = st.columns(4)
    a.write(f"**Last bot cycle:** {fmt_time(bot_status.get('last_cycle'))}")
    b.write(f"**Last scan completed:** {fmt_time(bot_status.get('last_scan_completed'))}")
    c.write(f"**Heartbeat:** {fmt_time(bot_status.get('heartbeat'))}")
    d.write(f"**Worker ID:** {bot_status.get('worker_id') or '—'}")
    st.write(f"**Status message:** {bot_status.get('message') or '—'}")
    if bot_status.get("error"):
        st.error(str(bot_status["error"]))

with st.expander("Strategy Configuration", expanded=False):
    st.write(f"**Universe:** NIFTY 100")
    st.write(f"**Pre-09:45 candidate filter:** liquidity + previous-day direction + today's opening gap")
    st.write(f"**Strategy:** GAP_FAILURE_OPEN_RECLAIM")
    st.write(f"**Entry window:** {TRADING_START}–{LAST_ENTRY_TIME} IST")
    st.write(f"**Mandatory square-off:** {SQUARE_OFF_TIME} IST")
    st.write(f"**Risk:** ₹{MIN_REQUIRED_RISK:,.0f}–₹{MAX_RISK_PER_TRADE:,.0f} per trade")
    st.write(f"**R:R:** 1:{RISK_REWARD_RATIO:g}")
    st.write(f"**Maximum positions:** {MAX_OPEN_POSITIONS}")
    st.write(f"**Paper:** {PAPER_TRADING} • **Live:** {LIVE_TRADING}")
