import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from worker_service import ensure_worker_process

ROOT = Path(__file__).resolve().parents[2]
INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="📌", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def read(path, kind):
    try:
        return json.loads(path.read_text()) if kind == "json" else pd.read_csv(path)
    except Exception:
        return {} if kind == "json" else pd.DataFrame()


def grid(items):
    html = "<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def heartbeat_alive(value, max_age_seconds=90):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        return 0 <= (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() <= max_age_seconds
    except Exception:
        return False


status = read(ROOT / "outputs/bot_status.json", "json")
try:
    live = ensure_worker_process()
    if isinstance(live, dict):
        status.update(live)
except Exception as error:
    status.setdefault("error", f"Worker launcher: {type(error).__name__}: {error}")

state = read(ROOT / "outputs/paper_engine_state.json", "json")
trades = read(ROOT / "outputs/trades.csv", "csv")
diag = read(ROOT / "outputs/scanner_diagnostics.json", "json")
gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
pos = state.get("open_positions", {}) if isinstance(state, dict) else {}
closed = trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
if not closed.empty and "pnl" in closed.columns:
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0)
worker = bool(status.get("worker_alive")) and heartbeat_alive(status.get("heartbeat"))

st.title("📌 Current Trading")
st.caption("NIFTY 500 • pre-9:45 gap preparation → PDH/PDL reaction → today's Open 1-minute reversal")
grid([
    ("Bot", status.get("status", "WAITING")),
    ("Worker", "ALIVE" if worker else "OFFLINE"),
    ("Open Positions", len(pos)),
    ("Available Capital", f"₹{float(status.get('available_capital', 250000) or 0):,.0f}"),
    ("Last Scan", status.get("last_scan_completed", "—")),
    ("Scan Duration", f"{float(status.get('scan_duration_seconds', 0) or 0):.1f}s"),
])
if status.get("error"):
    st.warning(str(status.get("error")))

st.subheader("Pre-9:45 Gap Board")
if not gaps.empty and "GapType" in gaps.columns:
    g = gaps.copy()
    g["GapPercent"] = pd.to_numeric(g["GapPercent"], errors="coerce")
    ups = g[g["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False)
    downs = g[g["GapType"].eq("GAP_DOWN")].sort_values("GapPercent")
    a, b = st.columns(2)
    with a:
        st.markdown("**🟢 Gap Ups**")
        st.dataframe(ups[[c for c in ["Symbol","PreviousClose","TodayOpen","GapPercent","PDH","PDL"] if c in ups.columns]].head(25), width="stretch", hide_index=True, height=320)
    with b:
        st.markdown("**🔴 Gap Downs**")
        st.dataframe(downs[[c for c in ["Symbol","PreviousClose","TodayOpen","GapPercent","PDH","PDL"] if c in downs.columns]].head(25), width="stretch", hide_index=True, height=320)
else:
    st.info("Gap board will be prepared automatically during the pre-entry phase and completed before 09:45 IST.")

st.subheader("Open Positions")
if pos:
    rows = []
    for symbol, p in pos.items():
        rows.append({"Stock": symbol, "Side": p.get("signal", ""), "Entry": p.get("entry"), "SL": p.get("stop_loss"), "Target": p.get("target"), "Qty": p.get("quantity"), "Risk": p.get("actual_risk", p.get("risk")), "R:R": p.get("rr", 1.25), "Entry Time": p.get("entry_time"), "Trigger Time": p.get("trigger_entry_time", "—"), "Setup": p.get("setup_type", "NIFTY_500_PDH_PDL_OPEN_REVERSAL"), "Gap %": p.get("gap_percent", "—"), "PDH": p.get("pdh", "—"), "PDL": p.get("pdl", "—"), "Open": p.get("today_open", "—")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No open paper positions.")

st.subheader("Scanner Filter Breakdown")
if isinstance(diag, dict) and diag:
    grid([
        ("NIFTY 500 Scanned", diag.get("stocks_scanned", 0)),
        ("Gap Data Ready", diag.get("gap_data_count", 0)),
        ("Gap Ups", diag.get("gap_up_count", 0)),
        ("Gap Downs", diag.get("gap_down_count", 0)),
        ("Liquidity Passed", diag.get("liquidity_passed", 0)),
        ("PDH / PDL Open Setup", diag.get("opening_setup_passed", 0)),
        ("NIFTY Market Alignment", diag.get("market_alignment_passed", 0)),
        ("Sector Alignment", diag.get("sector_alignment_passed", 0)),
        ("Strategy Setup", diag.get("strategy_setup_passed", 0)),
        ("Stock Alignment", diag.get("stock_alignment_passed", 0)),
        ("FINAL SIGNALS", diag.get("final_signals", 0)),
    ])
    labels = [("PDH / PDL not reached", "pdh_pdl_not_reached"), ("No Open Cross", "no_open_cross"), ("Sector Alignment", "sector_alignment"), ("Stock Alignment", "stock_alignment"), ("Strategy Setup", "strategy_setup"), ("NIFTY Alignment", "market_alignment"), ("Opening Setup", "opening_setup"), ("Liquidity", "liquidity"), ("Missing Data", "missing_data")]
    ranked = sorted(((label, int((diag.get("rejections", {}) or {}).get(key, 0) or 0)) for label, key in labels), key=lambda x: x[1], reverse=True)
    ranked = [x for x in ranked if x[1] > 0]
    if ranked:
        st.subheader("Top Rejection Reasons")
        grid(ranked)
else:
    st.info("Scanner diagnostics will appear after the next cycle.")

st.subheader("Latest Closed Trade")
if not closed.empty:
    t = closed.iloc[-1]
    grid([("Stock", t.get("symbol", "—")), ("Side", t.get("signal", "—")), ("Entry", t.get("entry", "—")), ("Exit", t.get("exit_price", "—")), ("P&L", f"₹{float(t.get('pnl', 0) or 0):,.2f}"), ("Exit Reason", t.get("exit_reason", "—")), ("PDH", t.get("pdh", "—")), ("PDL", t.get("pdl", "—")), ("Open", t.get("today_open", "—")), ("Gap %", t.get("gap_percent", "—")), ("Setup", t.get("setup_type", "—")), ("Sector", t.get("sector", "—")), ("Market", t.get("market_direction", "—"))])
else:
    st.info("No closed paper trade yet.")

st.subheader("Recent Trades")
if not trades.empty:
    st.dataframe(trades.iloc[::-1].head(30), width="stretch", hide_index=True)
else:
    st.info("No trades recorded yet.")
render_daily_footer()
