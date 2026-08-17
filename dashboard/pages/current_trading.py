import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from bot_runner import ensure_bot_running
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from market.price_data import PriceData
from strategy.contracts import strategy_metadata

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"

st.set_page_config(page_title="NSE Catalyst | Live Command Center", page_icon="🎯", layout="wide")
st_autorefresh(interval=5000, key="live_command_center")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def read(path, kind="json"):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if kind == "json" else pd.read_csv(path)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def price(value):
    try: return f"₹{float(value):,.2f}"
    except Exception: return "—"


def pct(value):
    try: return f"{float(value):+.2f}%"
    except Exception: return "—"


def age_seconds(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=INDIA_TZ)
        return max(0, int((datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None


def health_label(ok, good="🟢 HEALTHY", bad="🔴 NOT SAFE"):
    return good if ok else bad


def metric_cards(items):
    html = "<div class='metric-grid'>"
    for label, value in items:
        html += f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


status = read(ROOT / "outputs/bot_status.json")
diag = read(ROOT / "outputs/scanner_diagnostics.json")
state = read(ROOT / "outputs/paper_engine_state.json")
waiting = read(ROOT / "outputs/waiting_candidates.json")
gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
signals = read(ROOT / "outputs/signals.csv", "csv")
s2diag = read(ROOT / "outputs/strategy2_diagnostics.json")

try:
    live_status = ensure_bot_running()
    if isinstance(live_status, dict): status.update(live_status)
except Exception as error:
    status["error"] = f"Worker launcher: {type(error).__name__}: {error}"

now = datetime.now(INDIA_TZ)
clock = now.strftime("%H:%M")
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

try:
    pdx = PriceData()
    idx = pdx.get_index_1m("^CRSLDX")
    nifty_value = None if idx.empty else float(idx.iloc[-1]["Close"])
    nifty_change = pdx.get_index_change_pct("^CRSLDX")
    nifty_change = None if nifty_change is None else float(nifty_change)
except Exception:
    nifty_value, nifty_change = None, None

raw_change = diag.get("nifty500_change_pct")
if nifty_change is None and raw_change not in (None, ""):
    try: nifty_change = float(raw_change)
    except Exception: nifty_change = None

threshold = float(diag.get("coverage_required", 0.60) or 0.60)
market_threshold = 0.25
permission = "🟢 BUY" if nifty_change is not None and nifty_change >= market_threshold else "🔴 SELL" if nifty_change is not None and nifty_change <= -market_threshold else "⚪ WAIT"
window = "PREPARE" if clock < ENTRY_START else "ACTIVE" if clock <= ENTRY_END else "CLOSED"
heartbeat_age = age_seconds(status.get("heartbeat"))
data_age = age_seconds(diag.get("timestamp"))
worker_ok = bool(status.get("worker_alive")) and heartbeat_age is not None and heartbeat_age <= 90
data_coverage = float(diag.get("market_data_coverage", 0) or 0)
data_ok = data_coverage >= threshold and diag.get("data_quality") != "NO_DATA"

st.title("🎯 NSE Catalyst — Live Command Center")
st.caption(f"One source of truth • strategy-driven pipeline • paper trading • {now.strftime('%d %b %Y %H:%M:%S')} IST")

metric_cards([
    ("SYSTEM WORKER", health_label(worker_ok, "🟢 RUNNING", "🔴 STOPPED / STALE")),
    ("NIFTY 500", price(nifty_value) if nifty_value is not None else "Unavailable"),
    ("NIFTY CHANGE", pct(nifty_change) if nifty_change is not None else "Unavailable"),
    ("MARKET FILTER", permission),
    ("ENTRY WINDOW", window),
    ("OPEN POSITIONS", len(positions)),
])

if status.get("error"):
    st.error(str(status["error"]))

st.subheader("🩺 System & Data Health")
health = pd.DataFrame([
    ("Worker heartbeat", "PASS" if worker_ok else "FAIL", f"{heartbeat_age}s ago" if heartbeat_age is not None else "missing"),
    ("Scanner diagnostics", "PASS" if data_age is not None and data_age <= 90 else "FAIL", f"{data_age}s ago" if data_age is not None else "missing"),
    ("Reference data", "PASS" if int(diag.get("reference_data_count", 0) or 0) > 0 else "FAIL", str(diag.get("reference_data_count", 0))),
    ("1m market coverage", "PASS" if data_ok else "FAIL", f"{data_coverage:.1%} / required {threshold:.0%}"),
    ("NIFTY 500 feed", "PASS" if nifty_change is not None else "FAIL", pct(nifty_change)),
    ("Strategy version", "PASS", str(diag.get("strategy_version", "unknown"))),
], columns=["Check", "Status", "Detail"])
st.dataframe(health, width="stretch", hide_index=True)

st.subheader("🔗 Decision Pipeline")
scanned = int(diag.get("stocks_scanned", 0) or 0)
refs = int(diag.get("reference_data_count", 0) or 0)
gap_count = int(diag.get("gap_data_count", 0) or 0)
open_setup = int(diag.get("opening_setup_passed", 0) or 0)
aligned = int(diag.get("market_alignment_passed", 0) or 0)
qualified = int(diag.get("strategy_setup_passed", 0) or 0)
final_signals = int(diag.get("final_signals", 0) or 0)
approved = 0
if not signals.empty and "approved" in signals.columns:
    approved = int(signals["approved"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())

pipeline = pd.DataFrame([
    ("1. Universe", scanned, "stocks scanned"),
    ("2. Reference", refs, "PDH / PDL / PDC / Open"),
    ("3. Gap board", gap_count, "current open classified"),
    ("4. Opening setup", open_setup, "gap above PDH / below PDL"),
    ("5. Market alignment", aligned, "BUY / SELL side allowed"),
    ("6. Strategy qualified", qualified, "completed 1m sequence"),
    ("7. Final signals", final_signals, "fresh price + entry rule"),
    ("8. Risk approved", approved, "risk engine accepted"),
], columns=["Stage", "Count", "Meaning"])
st.dataframe(pipeline, width="stretch", hide_index=True)

if not data_ok and scanned:
    st.warning(f"NO TRADE SAFETY GATE: 1-minute market coverage is {data_coverage:.1%}, below the required {threshold:.0%}. The scanner will not qualify new Strategy 1 signals until coverage recovers.")

st.subheader("📐 Authoritative Strategy Rules")
for key in ("STRATEGY_1", "STRATEGY_2"):
    meta = strategy_metadata(key)
    with st.expander(f"{meta['strategy']} — {meta['name']} — v{meta['version']}", expanded=(key == "STRATEGY_1")):
        st.dataframe(pd.DataFrame(meta["rules"], columns=["Rule", "Definition"]), width="stretch", hide_index=True)

st.subheader("⏳ Waiting & Qualified Stocks")
waiting_rows = []
for side in ("BUY", "SELL"):
    for symbol, item in (waiting.get("waiting", {}).get(side, {}) or {}).items():
        waiting_rows.append({"Side": side, "Stock": symbol, "State": item.get("state", "WAITING"), "Gap %": item.get("gap_percent", 0), "Open": price(item.get("today_open")), "PDH": price(item.get("pdh")), "PDL": price(item.get("pdl")), "Strategy": item.get("strategy_version", diag.get("strategy_version", "—"))})
if waiting_rows:
    df = pd.DataFrame(waiting_rows); df["Gap %"] = pd.to_numeric(df["Gap %"], errors="coerce"); df = df.sort_values("Gap %", key=lambda s: s.abs(), ascending=False)
    st.dataframe(df, width="stretch", hide_index=True, height=320)
else:
    st.info("No Strategy 1 stocks are currently waiting for the next state transition.")

qualified_rows = []
for side in ("BUY", "SELL"):
    for symbol, item in (waiting.get("qualified", {}).get(side, {}) or {}).items():
        qualified_rows.append({"Side": side, "Stock": symbol, "Qualified": item.get("qualified_at", "—"), "Gap %": item.get("gap_percent", 0), "Open": price(item.get("today_open")), "PDH": price(item.get("pdh")), "PDL": price(item.get("pdl"))})
if qualified_rows:
    qdf = pd.DataFrame(qualified_rows); qdf["Gap %"] = pd.to_numeric(qdf["Gap %"], errors="coerce"); qdf = qdf.sort_values("Gap %", key=lambda s: s.abs(), ascending=False)
    st.dataframe(qdf, width="stretch", hide_index=True, height=260)
else:
    st.info("No Strategy 1 candidate has completed its breach → return sequence yet.")

st.subheader("🏆 Gap Board — Largest Absolute Gap First")
if not gaps.empty and "GapType" in gaps.columns:
    board = gaps.copy()
    for c in ("TodayOpen", "PDH", "PDL", "Gap", "GapPercent"):
        if c in board.columns: board[c] = pd.to_numeric(board[c], errors="coerce")
    board["Priority"] = board["GapPercent"].abs()
    up, down = board[board["GapType"].eq("GAP_UP")].sort_values("Priority", ascending=False), board[board["GapType"].eq("GAP_DOWN")].sort_values("Priority", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 GAP UP — Strategy 1 BUY candidates**")
        view = up[[c for c in ["Symbol", "Industry", "TodayOpen", "PDH", "GapPercent"] if c in up.columns]].head(25).copy()
        if not view.empty:
            for c in ("TodayOpen", "PDH"):
                if c in view: view[c] = view[c].map(price)
            if "GapPercent" in view: view["GapPercent"] = view["GapPercent"].map(pct)
            st.dataframe(view, width="stretch", hide_index=True, height=360)
        else: st.info("No gap-up candidates.")
    with c2:
        st.markdown("**🔴 GAP DOWN — Strategy 1 SELL candidates**")
        view = down[[c for c in ["Symbol", "Industry", "TodayOpen", "PDL", "GapPercent"] if c in down.columns]].head(25).copy()
        if not view.empty:
            for c in ("TodayOpen", "PDL"):
                if c in view: view[c] = view[c].map(price)
            if "GapPercent" in view: view["GapPercent"] = view["GapPercent"].map(pct)
            st.dataframe(view, width="stretch", hide_index=True, height=360)
        else: st.info("No gap-down candidates.")
else:
    st.info("Gap board has not been prepared yet.")

st.subheader("🚨 Today's Approved Signals")
if not signals.empty:
    frame = signals.copy()
    date_col = "entry_time" if "entry_time" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
    if date_col:
        dates = pd.to_datetime(frame[date_col], errors="coerce")
        if getattr(dates.dt, "tz", None) is None: dates = dates.dt.tz_localize(INDIA_TZ)
        else: dates = dates.dt.tz_convert(INDIA_TZ)
        frame = frame.loc[dates.dt.date.eq(now.date())].copy()
    if "approved" in frame.columns:
        frame = frame[frame["approved"].astype(str).str.lower().isin(["true", "1", "yes"])]
    cols = [c for c in ["strategy", "strategy_version", "symbol", "signal", "entry_time", "entry", "stop_loss", "target", "quantity", "gap_percent", "priority_rank"] if c in frame.columns]
    if not frame.empty and cols: st.dataframe(frame[cols].tail(25).iloc[::-1], width="stretch", hide_index=True)
    else: st.info("No approved signals today.")
else:
    st.info("No approved signals today.")

st.subheader("📍 Open Paper Positions")
if positions:
    rows = []
    pdx = PriceData()
    for symbol, position in positions.items():
        try:
            latest = pdx.get_latest_market_price(symbol); ltp = latest.get("Close") if latest else None
        except Exception: ltp = None
        entry = position.get("entry"); side = str(position.get("signal", "")).upper(); pnl = None
        try:
            qty = float(position.get("quantity", 0) or 0)
            pnl = ((float(ltp) - float(entry)) * qty if side == "BUY" else (float(entry) - float(ltp)) * qty) if ltp is not None and entry is not None else None
        except Exception: pass
        rows.append({"Stock": symbol, "Strategy": position.get("strategy", "STRATEGY_1"), "Side": side, "Entry": price(entry), "LTP": price(ltp), "Live P&L": price(pnl), "SL": price(position.get("stop_loss")), "Target": price(position.get("target")), "Qty": position.get("quantity", "—")})
    st.dataframe(pd.DataFrame(rows).astype(str), width="stretch", hide_index=True)
else:
    st.info("No open paper positions.")

st.subheader("🧪 Strategy 2 Runtime")
if isinstance(s2diag, dict) and s2diag:
    metric_cards([("S2 STATUS", "🟢 ACTIVE" if s2diag.get("signals", 0) >= 0 else "—"), ("S2 VERSION", s2diag.get("strategy_version", "—")), ("S2 QUALIFIED", s2diag.get("qualified", 0)), ("S2 SIGNALS", s2diag.get("signals", 0)), ("S2 OPEN", s2diag.get("open_positions", 0)), ("S2 DAILY P&L", price(s2diag.get("daily_pnl", 0)))])
else:
    st.info("Strategy 2 diagnostics are not available yet.")

st.caption(f"Worker heartbeat: {status.get('heartbeat', '—')} • Last scan: {status.get('last_scan_completed', '—')} • Scan error: {status.get('last_scan_error') or 'None'} • Auto-refresh 5s • Paper trading only")
render_daily_footer()
