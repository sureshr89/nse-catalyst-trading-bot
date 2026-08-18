"""Strategy 1 live command center with clear market alignment and responsive views."""
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
from config.settings import NIFTY500_MIN_CHANGE_PCT
from strategy.contracts import strategy_metadata

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"
NIFTY500_TICKER = "^CRSLDX"

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


def alignment_panel(nifty, change, threshold, data_age, scan_age):
    if change is None:
        direction, reason = "UNAVAILABLE", "NIFTY 500 live change is unavailable"
        buy, sell = False, False
    else:
        buy, sell = float(change) >= threshold, float(change) <= -threshold
        direction = "BULLISH" if buy else "BEARISH" if sell else "NEUTRAL"
        reason = f"BUY ≥ +{threshold:.2f}% • SELL ≤ -{threshold:.2f}%"
    st.markdown(f"""
    <section class='alignment-panel'>
      <div class='alignment-head'><div><strong>Market Alignment</strong><span>NIFTY 500 gate checked before Strategy 1 entry</span></div><b>{direction}</b></div>
      <div class='alignment-grid'>
        <div class='alignment-item'><small>NIFTY 500</small><strong>{money(nifty)}</strong><span>{pct(change)}</span></div>
        <div class='alignment-item'><small>BUY</small><strong>{'ALIGNED ✓' if buy else 'BLOCKED'}</strong><span>Open &gt; PDH setup</span></div>
        <div class='alignment-item'><small>SELL</small><strong>{'ALIGNED ✓' if sell else 'BLOCKED'}</strong><span>Open &lt; PDL setup</span></div>
        <div class='alignment-item'><small>THRESHOLD</small><strong>±{threshold:.2f}%</strong><span>{reason}</span></div>
      </div>
      <div class='alignment-foot'>Index: {NIFTY500_TICKER} • Index data age: {data_age if data_age is not None else '—'}s • Scanner age: {scan_age if scan_age is not None else '—'}s</div>
    </section>
    """, unsafe_allow_html=True)


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
    idx = pdx.get_index_1m(NIFTY500_TICKER)
    nifty = None if idx.empty else float(idx.iloc[-1]["Close"])
    nifty_change = pdx.get_index_change_pct(NIFTY500_TICKER, intraday=idx)
    index_stamp = None if idx.empty else idx.iloc[-1].get("Datetime")
    index_age = age(index_stamp.isoformat() if hasattr(index_stamp, "isoformat") else index_stamp)
except Exception:
    nifty, nifty_change, index_age = None, None, None

meta = strategy_metadata("STRATEGY_1")
st.title("🔵 Strategy 1 — Current Trading")
st.caption(f"{meta['name']} • {meta['version']} • LIVE LTP entry / SL / target • no candle-close confirmation • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([
    ("WORKER", "🟢 RUNNING" if worker_ok else "🔴 STALE"), ("NIFTY 500", money(nifty)), ("NIFTY CHANGE", pct(nifty_change)),
    ("ENTRY WINDOW", window), ("OPEN POSITIONS", len(positions)), ("REALIZED DAILY P&L", money(status.get("daily_pnl", status.get("session_pnl", 0)))),
    ("LAST SCAN", f"{scan_age}s ago" if scan_age is not None else "—"), ("EXIT MONITOR", "~2s LIVE"),
])
alignment_panel(nifty, nifty_change, NIFTY500_MIN_CHANGE_PCT, index_age, scan_age)

if status.get("error") or status.get("last_scan_error"):
    st.error(str(status.get("error") or status.get("last_scan_error")))

st.subheader("🔎 Scanner — Live Data Alignment")
risk_approved = 0
if not signals.empty and "approved" in signals.columns:
    risk_approved = int(signals["approved"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
cards([
    ("STOCKS SCANNED", diag.get("stocks_scanned", 0)), ("REFERENCE DATA", diag.get("reference_data_count", 0)),
    ("OPENING SETUPS", diag.get("opening_setup_passed", 0)), ("MARKET ALIGNMENT", diag.get("market_alignment_passed", 0)),
    ("QUALIFIED", diag.get("strategy_setup_passed", 0)), ("FINAL SIGNALS", diag.get("final_signals", 0)),
    ("RISK APPROVED", risk_approved), ("1m COVERAGE", f"{coverage:.0%}"),
])
if coverage < required and int(diag.get("stocks_scanned", 0) or 0) > 0:
    st.warning(f"Scanner safety gate: 1-minute coverage {coverage:.0%} is below required {required:.0%}. No new entries should be trusted until coverage recovers.")

with st.expander("📋 Scanner Pipeline & Alignment", expanded=False):
    pipeline = pd.DataFrame([
        ("Universe", diag.get("stocks_scanned", 0), "NIFTY 500 stocks", "DATA"),
        ("Reference", diag.get("reference_data_count", 0), "PDH / PDL / PDC / Open", "DATA"),
        ("Opening setup", diag.get("opening_setup_passed", 0), "Open above PDH / below PDL", "SETUP"),
        ("Market alignment", diag.get("market_alignment_passed", 0), f"NIFTY 500 ≥ +{NIFTY500_MIN_CHANGE_PCT:.2f}% BUY or ≤ -{NIFTY500_MIN_CHANGE_PCT:.2f}% SELL", "GATE"),
        ("Strategy qualified", diag.get("strategy_setup_passed", 0), "Live price reached breach + returned to Open", "LIVE LTP"),
        ("Final signals", diag.get("final_signals", 0), "Live entry + risk checks", "ENTRY"),
    ], columns=["Stage", "Count", "Rule / Data", "Type"])
    st.dataframe(pipeline, width="stretch", hide_index=True)

with st.expander("⏳ Waiting / Qualified Stocks", expanded=False):
    rows = []
    for side in ("BUY", "SELL"):
        waiting_items = (waiting.get("waiting", {}).get(side, {}) or {}) if isinstance(waiting, dict) else {}
        qualified_items = (waiting.get("qualified", {}).get(side, {}) or {}) if isinstance(waiting, dict) else {}
        for collection_name, items in (("WAITING", waiting_items), ("QUALIFIED", qualified_items)):
            if not isinstance(items, dict): continue
            for symbol, item in items.items():
                if isinstance(item, dict):
                    rows.append({"Side": side, "Stock": symbol, "State": item.get("state", collection_name), "Open": money(item.get("today_open")), "PDH": money(item.get("pdh")), "PDL": money(item.get("pdl")), "Gap %": pct(item.get("gap_percent", 0)), "Breach": "YES" if item.get("pdh_breached") or item.get("pdl_breached") else "NO", "Qualified At": item.get("qualified_time") or item.get("qualified_at") or "—"})
    if rows: st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=340)
    else: st.info("No stocks currently waiting for a live state transition.")

with st.expander("🚨 Today's Approved Signals", expanded=False):
    frame = signals.copy()
    if not frame.empty:
        date_col = "entry_time" if "entry_time" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
        if date_col:
            dates = pd.to_datetime(frame[date_col], errors="coerce")
            dates = dates.dt.tz_localize(INDIA_TZ) if dates.dt.tz is None else dates.dt.tz_convert(INDIA_TZ)
            frame = frame.loc[dates.dt.date.eq(now.date())]
        if "approved" in frame.columns: frame = frame[frame["approved"].astype(str).str.lower().isin(["true", "1", "yes"])]
        cols = [c for c in ["strategy", "symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk_reward", "entry_source", "priority_rank"] if c in frame.columns]
        if not frame.empty and cols: st.dataframe(frame[cols].tail(25).iloc[::-1], width="stretch", hide_index=True)
        else: st.info("No approved signals today.")
    else: st.info("No approved signals today.")

st.subheader("📍 Open Paper Positions")
st.caption("LTP, SL and target are monitored independently of candle close. Entry and exit times are stored in IST with millisecond precision.")
if positions:
    pdx = PriceData(); rows = []
    for symbol, position in positions.items():
        try:
            live = pdx.get_latest_live_price(symbol, max_age_seconds=3); ltp = live.get("Close") if live else None
        except Exception:
            live, ltp = None, None
        entry = position.get("entry"); side = str(position.get("signal", "")).upper(); qty = int(float(position.get("quantity", 0) or 0)); pnl = None
        try:
            if ltp is not None and entry is not None: pnl = ((float(ltp) - float(entry)) * qty) if side == "BUY" else ((float(entry) - float(ltp)) * qty)
        except Exception: pass
        rows.append({"Strategy": position.get("strategy", "STRATEGY_1"), "Stock": symbol, "Side": side, "Entry": money(entry), "LTP": money(ltp), "Live P&L": money(pnl), "SL": money(position.get("stop_loss")), "Target": money(position.get("target")), "Qty": qty, "Risk": money(position.get("actual_risk", position.get("risk"))), "Entry Time": position.get("entry_time", "—"), "Price Data": live.get("price_source", "LIVE") if live else "STALE/UNAVAILABLE"})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else: st.info("No open Strategy 1 paper positions.")

st.caption(f"Heartbeat: {status.get('heartbeat','—')} • Last scan: {diag.get('timestamp','—')} • Position exit monitor: every ~2s • UI refresh: 5s")
render_nav()
render_daily_footer()
