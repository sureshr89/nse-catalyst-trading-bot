import json, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running

INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Stock Scanner", page_icon="🔎", layout="wide")
st_autorefresh(interval=5000, key="stock_scanner_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def money(v):
    try: return f"₹{float(v):,.2f}"
    except Exception: return "—"

def pct(v):
    try: return f"{float(v):+.2f}%"
    except Exception: return "—"

def metric_cards(items):
    html = "<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>" for label, value in items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

gaps = read_csv(ROOT / "outputs/gap_analysis.csv")
waiting = read_json(ROOT / "outputs/waiting_candidates.json")
state = read_json(ROOT / "outputs/paper_engine_state.json")
diag = read_json(ROOT / "outputs/scanner_diagnostics.json")
news = read_csv(ROOT / "outputs/MASTER_NEWS_ANALYSIS.csv")
try:
    ensure_bot_running()
except Exception:
    pass
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
market_change = float(diag.get("nifty500_change_pct", 0) or 0)
now = datetime.now(INDIA_TZ)
waiting_data = waiting.get("waiting", {}) if isinstance(waiting, dict) else {}
qualified_data = waiting.get("qualified", {}) if isinstance(waiting, dict) else {}

st.title("🔎 NIFTY 500 Stock Scanner")
st.caption("Workflow: highest qualifying GAP first → ATR% second → strategy/risk/news validation → paper entry")
metric_cards([
    ("BUY waiting", len(waiting_data.get("BUY", {}))),
    ("SELL waiting", len(waiting_data.get("SELL", {}))),
    ("BUY qualified", len(qualified_data.get("BUY", {}))),
    ("SELL qualified", len(qualified_data.get("SELL", {}))),
])
st.caption(f"NIFTY 500 {market_change:+.2f}% • 1-minute completed-candle logic • Updated {now.strftime('%H:%M:%S')} IST")

st.subheader("🏆 Priority Ranking — Highest Gap First")
ranks = pd.DataFrame(diag.get("ranking", []) if isinstance(diag, dict) else [])
if not ranks.empty:
    for col in ["gap_percent", "atr_pct", "gap_priority_pct"]:
        if col in ranks.columns: ranks[col] = pd.to_numeric(ranks[col], errors="coerce")
    display_cols = [c for c in ["priority", "symbol", "side", "gap_percent", "gap_priority_pct", "atr_pct", "candidate_state"] if c in ranks.columns]
    view = ranks[display_cols].copy()
    rename = {"priority":"Priority", "symbol":"Symbol", "side":"Side", "gap_percent":"Gap %", "gap_priority_pct":"Gap Priority %", "atr_pct":"ATR %", "candidate_state":"State"}
    view.rename(columns={k:v for k,v in rename.items() if k in view.columns}, inplace=True)
    st.dataframe(view, width="stretch", hide_index=True, height=360)
    st.caption("Priority is strictly ordered by absolute qualifying gap %. ATR% is the secondary tie-breaker.")
else:
    st.info("No qualified candidates yet.")

st.subheader("⏳ Waiting Stocks")
waiting_rows = []
for side in ("BUY", "SELL"):
    for symbol, item in waiting_data.get(side, {}).items():
        waiting_rows.append({"Side":side,"Symbol":symbol,"State":item.get("state","WAITING"),"Gap %":item.get("gap_percent",0),"Today's Open":money(item.get("today_open")),"PDH":money(item.get("pdh")),"PDL":money(item.get("pdl")),"Created":item.get("created_at","—")})
if waiting_rows:
    wdf = pd.DataFrame(waiting_rows).sort_values(["Gap %", "Side"], key=lambda s: s.abs() if s.name == "Gap %" else s, ascending=False)
    st.dataframe(wdf, width="stretch", hide_index=True, height=360)
else:
    st.info("No stocks are currently waiting for the required breach/return sequence.")

st.subheader("📊 Gap / Opening Board")
if gaps.empty:
    st.info("Gap board will appear when market data is available.")
else:
    board = gaps.copy()
    for c in ["GapPercent", "GapPercentFromPreviousClose"]:
        if c in board.columns: board[c] = pd.to_numeric(board[c], errors="coerce")
    if "GapPercent" in board.columns: board["GapPriority"] = board["GapPercent"].abs()
    sort_cols = [c for c in ["GapPriority", "GapPercent"] if c in board.columns]
    if sort_cols: board = board.sort_values(sort_cols, ascending=False, na_position="last")
    preferred = [c for c in ["Symbol","Industry","TodayOpen","PreviousClose","GapType","GapPercent","GapPercentFromPreviousClose","PDH","PDL"] if c in board.columns]
    view = board[preferred].copy()
    for c in ["TodayOpen","PreviousClose","PDH","PDL"]:
        if c in view.columns: view[c] = view[c].map(money)
    for c in ["GapPercent","GapPercentFromPreviousClose"]:
        if c in view.columns: view[c] = view[c].map(pct)
    st.dataframe(view, width="stretch", hide_index=True, height=520)

st.subheader("📰 Final News Decisions")
if not news.empty:
    cols = [c for c in ["timestamp","symbol","signal","news_sentiment","news_confidence","news_headline","news_reason","approved"] if c in news.columns]
    if cols: st.dataframe(news[cols].tail(30).iloc[::-1], width="stretch", hide_index=True, height=320)
    else: st.info("No news decision columns available.")
else:
    st.info("No news decisions recorded yet.")

st.caption("Strategy conditions remain unchanged: qualifying gap → PDH/PDL breach → return to Today's Open using completed 1-minute CLOSE → current-price/risk validation. Industry/Sector is informational only. Paper trading only.")
render_daily_footer()
