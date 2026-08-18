"""Strategy 1 live command center with scanner details and live positions."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_runner import ensure_bot_running
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"

st.set_page_config(page_title="NSE Catalyst | Strategy 1 Current", page_icon="🔵", layout="wide")
st_autorefresh(interval=5000, key="s1_current_live")
st.markdown(load_css(), unsafe_allow_html=True)


def read(path, kind="json"):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if kind == "json" else pd.read_csv(path)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def money(v):
    try: return f"₹{float(v):,.2f}"
    except Exception: return "—"


def pct(v):
    try: return f"{float(v):+.2f}%"
    except Exception: return "—"


def age(v):
    try:
        stamp = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=INDIA_TZ) if stamp.tzinfo is None else stamp
        return max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None


def cards(items):
    html = "<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a, b in items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


try:
    launcher = ensure_bot_running() or {}
except Exception as error:
    launcher = {"error": f"Worker launcher: {type(error).__name__}: {error}"}

status = read(ROOT / "outputs/bot_status.json")
if isinstance(launcher, dict): status.update(launcher)
diag = read(ROOT / "outputs/scanner_diagnostics.json")
state = read(ROOT / "outputs/paper_engine_state.json")
signals = read(ROOT / "outputs/signals.csv", "csv")
waiting = read(ROOT / "outputs/waiting_candidates.json")
now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
heartbeat_age = age(status.get("heartbeat"))
scan_age = age(diag.get("timestamp"))
worker_ok = bool(status.get("worker_alive")) and heartbeat_age is not None and heartbeat_age <= 90
coverage = float(diag.get("market_data_coverage", 0) or 0)
required = float(diag.get("coverage_required", .60) or .60)
window = "PREPARE" if clock < ENTRY_START else "ACTIVE" if clock <= ENTRY_END else "CLOSED"

try:
    pdx = PriceData()
    idx = pdx.get_index_1m("^CRSLDX")
    nifty = None if idx.empty else float(idx.iloc[-1]["Close"])
    nifty_change = pdx.get_index_change_pct("^CRSLDX")
except Exception:
    nifty, nifty_change = None, None

st.title("🔵 Strategy 1 — Current Trading")
st.caption(f"PDH/PDL + Today's Open Return • paper trading only • {now.strftime('%d %b %Y %H:%M:%S')} IST")

cards([
    ("WORKER", "🟢 RUNNING" if worker_ok else "🔴 STALE"),
    ("NIFTY 500", money(nifty)),
    ("NIFTY CHANGE", pct(nifty_change)),
    ("ENTRY WINDOW", window),
    ("OPEN POSITIONS", len(positions)),
    ("REALIZED DAILY P&L", money(status.get("daily_pnl", status.get("session_pnl", 0)))),
    ("LAST SCAN", f"{scan_age}s ago" if scan_age is not None else "—"),
    ("EXIT MONITOR", "~2s LIVE"),
])

if status.get("error") or status.get("last_scan_error"):
    st.error(str(status.get("error") or status.get("last_scan_error")))

st.subheader("🔎 Scanner — Live Summary")
risk_approved = 0
if not signals.empty and "approved" in signals.columns:
    risk_approved = int(signals["approved"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
cards([
    ("STOCKS SCANNED", diag.get("stocks_scanned", 0)),
    ("REFERENCE DATA", diag.get("reference_data_count", 0)),
    ("GAP SETUPS", diag.get("opening_setup_passed", 0)),
    ("QUALIFIED", diag.get("strategy_setup_passed", 0)),
    ("FINAL SIGNALS", diag.get("final_signals", 0)),
    ("RISK APPROVED", risk_approved),
    ("1m COVERAGE", f"{coverage:.0%}"),
    ("SCAN AGE", f"{scan_age}s" if scan_age is not None else "—"),
])
if coverage < required and int(diag.get("stocks_scanned", 0) or 0) > 0:
    st.warning(f"Scanner safety gate: 1-minute coverage {coverage:.0%} is below required {required:.0%}.")

with st.expander("📋 Scanner Pipeline", expanded=False):
    pipeline = pd.DataFrame([
        ("Universe", diag.get("stocks_scanned", 0), "NIFTY 500"),
        ("Reference", diag.get("reference_data_count", 0), "PDH / PDL / PDC / Open"),
        ("Gap setup", diag.get("gap_data_count", 0), "Opening gap classification"),
        ("Opening setup", diag.get("opening_setup_passed", 0), "Open above PDH / below PDL"),
        ("Market alignment", diag.get("market_alignment_passed", 0), "NIFTY 500 directional gate"),
        ("Strategy qualified", diag.get("strategy_setup_passed", 0), "Completed price-action sequence"),
        ("Final signals", diag.get("final_signals", 0), "Fresh entry + risk checks"),
    ], columns=["Stage", "Count", "Meaning"])
    st.dataframe(pipeline, width="stretch", hide_index=True)

with st.expander("⏳ Waiting / Qualified Stocks", expanded=False):
    rows = []
    for side in ("BUY", "SELL"):
        items = (waiting.get("waiting", {}).get(side, {}) or {}) if isinstance(waiting, dict) else {}
        if not isinstance(items, dict): items = {}
        for symbol, item in items.items():
            if isinstance(item, dict):
                rows.append({"Side": side, "Stock": symbol, "State": item.get("state", "WAITING"), "Gap %": item.get("gap_percent", 0), "Open": money(item.get("today_open")), "PDH": money(item.get("pdh")), "PDL": money(item.get("pdl"))})
    if rows:
        frame = pd.DataFrame(rows); frame["Gap %"] = pd.to_numeric(frame["Gap %"], errors="coerce")
        st.dataframe(frame.sort_values("Gap %", key=lambda s: s.abs(), ascending=False), width="stretch", hide_index=True, height=300)
    else:
        st.info("No stocks currently waiting for a state transition.")

with st.expander("🚨 Today's Approved Signals", expanded=False):
    frame = signals.copy()
    if not frame.empty:
        date_col = "entry_time" if "entry_time" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
        if date_col:
            dates = pd.to_datetime(frame[date_col], errors="coerce")
            dates = dates.dt.tz_localize(INDIA_TZ) if dates.dt.tz is None else dates.dt.tz_convert(INDIA_TZ)
            frame = frame.loc[dates.dt.date.eq(now.date())]
        if "approved" in frame.columns:
            frame = frame[frame["approved"].astype(str).str.lower().isin(["true", "1", "yes"])]
        cols = [c for c in ["strategy", "symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_reward", "gap_percent", "priority_rank"] if c in frame.columns]
        if not frame.empty and cols:
            st.dataframe(frame[cols].tail(25).iloc[::-1], width="stretch", hide_index=True)
        else: st.info("No approved signals today.")
    else: st.info("No approved signals today.")

st.subheader("📍 Open Paper Positions")
st.caption("Live P&L is unrealized and changes with LTP. Realized P&L changes only after an exit is recorded.")
if positions:
    pdx = PriceData(); rows = []
    for symbol, position in positions.items():
        try:
            live = pdx.get_latest_live_price(symbol, max_age_seconds=3)
            ltp = live.get("Close") if live else None
            live_time = live.get("Datetime") if live else None
        except Exception:
            ltp = None; live_time = None
        entry = position.get("entry"); side = str(position.get("signal", "")).upper(); qty = int(float(position.get("quantity", 0) or 0)); pnl = None
        try:
            if ltp is not None and entry is not None:
                pnl = ((float(ltp) - float(entry)) * qty) if side == "BUY" else ((float(entry) - float(ltp)) * qty)
        except Exception: pass
        rows.append({
            "Strategy": "STRATEGY_1",
            "Stock": symbol,
            "Side": side,
            "Entry": money(entry),
            "LTP": money(ltp),
            "Live P&L": money(pnl),
            "SL": money(position.get("stop_loss")),
            "Target": money(position.get("target")),
            "Qty": qty,
            "Risk": money(position.get("actual_risk", position.get("risk"))),
            "Entry Time": position.get("entry_time", "—"),
            "Price Data": "LIVE" if live_time is not None else "STALE/UNAVAILABLE",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open Strategy 1 paper positions.")

st.caption(f"Heartbeat: {status.get('heartbeat','—')} • Last scan: {diag.get('timestamp','—')} • Position exit monitor: every ~2s • UI refresh: 5s")
render_nav()
render_daily_footer()
