import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from dashboard.nav import render_nav

ROOT = Path(__file__).resolve().parents[2]
INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="📌", layout="wide")
render_nav()


def read(path, kind):
    try:
        return json.loads(path.read_text()) if kind == "json" else pd.read_csv(path)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def grid(items):
    st.markdown("<div style='display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px'>" + "".join(f"<div style='background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px'><div style='font-size:.58rem;color:#9fb0c7'>{a}</div><div style='font-size:.84rem;color:#f4f7fb;font-weight:750;margin-top:3px'>{b}</div></div>" for a, b in items) + "</div>", unsafe_allow_html=True)


def heartbeat_alive(value, max_age_seconds=90):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=INDIA_TZ)
        return 0 <= (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() <= max_age_seconds
    except Exception:
        return False


status = read(ROOT / "outputs/bot_status.json", "json")
state = read(ROOT / "outputs/paper_engine_state.json", "json")
trades = read(ROOT / "outputs/trades.csv", "csv")
diag = read(ROOT / "outputs/scanner_diagnostics.json", "json")
pos = state.get("open_positions", {}) if isinstance(state, dict) else {}
closed = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns: closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0)
worker = bool(status.get("worker_alive")) and heartbeat_alive(status.get("heartbeat"))

st.title("📌 Current Trading")
st.caption("NIFTY 500 • PDH/PDL reaction → today's Open 1-minute reversal")
grid([("Bot", status.get("status", "WAITING")), ("Worker", "ALIVE" if worker else "OFFLINE"), ("Open Positions", len(pos)), ("Available Capital", f"₹{float(status.get('available_capital', 250000) or 0):,.0f}")])

st.subheader("Open Positions")
if pos:
    rows = []
    for symbol, p in pos.items():
        rows.append({"Stock": symbol, "Side": p.get("signal", ""), "Entry": p.get("entry"), "SL": p.get("stop_loss"), "Target": p.get("target"), "Qty": p.get("quantity"), "Risk": p.get("actual_risk", p.get("risk")), "R:R": p.get("rr", 1.25), "Entry Time": p.get("entry_time"), "Setup": p.get("setup_type", "NIFTY_500_PDH_PDL_OPEN_REVERSAL"), "PDH": p.get("pdh", "—"), "PDL": p.get("pdl", "—"), "Open": p.get("today_open", "—")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open paper positions.")

st.subheader("Scanner Filter Breakdown")
if diag:
    grid([
        ("NIFTY 500 Scanned", diag.get("stocks_scanned", 0)),
        ("Liquidity Passed", diag.get("liquidity_passed", 0)),
        ("PDH / PDL Open Setup", diag.get("opening_setup_passed", 0)),
        ("NIFTY Market Alignment", diag.get("market_alignment_passed", 0)),
        ("Sector Alignment", diag.get("sector_alignment_passed", 0)),
        ("Strategy Setup", diag.get("strategy_setup_passed", 0)),
        ("Stock Alignment", diag.get("stock_alignment_passed", 0)),
        ("FINAL SIGNALS", diag.get("final_signals", 0)),
    ])
    rejection_labels = [
        ("PDH / PDL not reached", "pdh_pdl_not_reached"),
        ("No Open Cross", "no_open_cross"),
        ("Sector Alignment", "sector_alignment"),
        ("Stock Alignment", "stock_alignment"),
        ("Strategy Setup", "strategy_setup"),
        ("NIFTY Alignment", "market_alignment"),
        ("Opening Setup", "opening_setup"),
        ("Liquidity", "liquidity"),
        ("Missing Data", "missing_data"),
    ]
    ranked = sorted(((label, int((diag.get("rejections", {}) or {}).get(key, 0) or 0)) for label, key in rejection_labels), key=lambda x: x[1], reverse=True)
    ranked = [x for x in ranked if x[1] > 0]
    if ranked: grid(ranked)
else:
    st.info("Scanner diagnostics will appear after the next cycle.")

st.subheader("Latest Closed Trade")
if not closed.empty:
    t = closed.iloc[-1]
    grid([("Stock", t.get("symbol", "—")), ("Side", t.get("signal", "—")), ("Entry", t.get("entry", "—")), ("Exit", t.get("exit_price", "—")), ("P&L", f"₹{float(t.get('pnl', 0) or 0):,.2f}"), ("Exit Reason", t.get("exit_reason", "—")), ("PDH", t.get("pdh", "—")), ("PDL", t.get("pdl", "—")), ("Open", t.get("today_open", "—")), ("Setup", t.get("setup_type", "—")), ("Sector", t.get("sector", "—")), ("Market", t.get("market_direction", "—"))])
else:
    st.info("No closed paper trade yet.")

st.subheader("Recent Trades")
if not trades.empty:
    st.dataframe(trades.iloc[::-1].head(30), width="stretch", hide_index=True)
else:
    st.info("No trades recorded yet.")
