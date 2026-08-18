from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from config import settings
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running, get_status
from dashboard.strategy2_data import status as strategy2_status
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Dashboard", page_icon=str(ROOT / "favicon.png"), layout="wide", initial_sidebar_state="collapsed")
st.markdown(load_css(), unsafe_allow_html=True)
st_autorefresh(interval=5000, key="dashboard_live")

startup_errors = []
try:
    ensure_bot_running()
except Exception as exc:
    startup_errors.append(f"Paper bot: {type(exc).__name__}: {exc}")

status = get_status() or {}
strategy2 = strategy2_status() or {}
render_nav()

@st.cache_data(ttl=20, show_spinner=False)
def live_nifty500():
    try:
        pdx = PriceData()
        candles = pdx.get_index_1m("^CRSLDX")
        value = None if candles.empty else float(candles.iloc[-1]["Close"])
        change = pdx.get_index_change_pct("^CRSLDX")
        return value, change
    except Exception:
        return None, None

nifty_value, nifty_change = live_nifty500()
now = pd.Timestamp.now(tz=INDIA_TZ)

st.title("📈 NSE Catalyst")
st.caption("Clean paper-trading command center • Strategy 1 and Strategy 2 remain completely independent")
for error in startup_errors:
    st.warning(error)

def cards(items):
    st.markdown("<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{label}</small><b>{value}</b></div>" for label, value in items) + "</div>", unsafe_allow_html=True)

def money(v):
    try: return f"₹{float(v):,.0f}"
    except Exception: return "—"

def pct(v):
    try: return f"{float(v):+.2f}%"
    except Exception: return "—"

s1_capital = float(status.get("available_capital", getattr(settings, "TOTAL_CAPITAL", 250000)) or 0)
s2_capital = float(strategy2.get("available_capital", 250000) or 0)
s1_status = str(status.get("status", "UNKNOWN"))
s2_status = str(strategy2.get("status", "STARTING"))

cards([
    ("NIFTY 500 VALUE", f"{nifty_value:,.2f}" if nifty_value is not None else "Unavailable"),
    ("NIFTY 500 CHANGE", pct(nifty_change) if nifty_change is not None else "Unavailable"),
    ("🔵 STRATEGY 1", s1_status),
    ("🔴 STRATEGY 2", s2_status),
    ("MARKET TIME", now.strftime("%H:%M:%S IST")),
])

if nifty_value is None or nifty_change is None:
    st.warning("NIFTY 500 live snapshot is currently unavailable. The bot will not use stale index data as a fresh live reading.")

st.subheader("🔵 Strategy 1 — PDH/PDL Return")
left, right = st.columns(2, gap="large")
with left:
    st.markdown("<div class='dashboard-info-card'><div class='info-row'><span>PRIORITY</span><b>Highest qualifying absolute GAP % first — no ATR</b></div><div class='info-row'><span>SETUP</span><b>Gap above PDH for BUY / gap below PDL for SELL</b></div><div class='info-row'><span>TRIGGER</span><b>Completed 1-minute CLOSE breaches PDH/PDL, then a later completed 1-minute CLOSE returns to Today's Open</b></div><div class='info-row'><span>SL</span><b>BUY = PDH • SELL = PDL</b></div><div class='info-row'><span>TARGET</span><b>1.25R • ₹1,400–₹1,500 intended risk • maximum 2 open positions</b></div></div>", unsafe_allow_html=True)
with right:
    st.markdown("<div class='dashboard-info-card'><div class='session-row'><span>Worker</span><b>" + s1_status + "</b></div><div class='session-row'><span>Heartbeat</span><b>" + str(status.get("heartbeat") or "Not available") + "</b></div><div class='session-row'><span>Last scan</span><b>" + str(status.get("last_scan_completed") or "Not scanned yet") + "</b></div><div class='session-row'><span>Signals</span><b>" + str(int(status.get("last_signal_count", 0) or 0)) + "</b></div><div class='session-row'><span>Capital</span><b>" + money(s1_capital) + "</b></div></div>", unsafe_allow_html=True)
if status.get("last_scan_error"):
    st.error(f"Strategy 1 scan error: {status['last_scan_error']}")

st.subheader("🔴 Strategy 2 — Gap Extension Reversal")
left, right = st.columns(2, gap="large")
with left:
    st.markdown("<div class='dashboard-info-card'><div class='info-row'><span>SELL</span><b>Open above PDH → extension → completed 1-minute CLOSE below Open</b></div><div class='info-row'><span>BUY</span><b>Open below PDL → extension → completed 1-minute CLOSE above Open</b></div><div class='info-row'><span>ENTRY</span><b>Completed trigger candle close</b></div><div class='info-row'><span>ACCOUNT</span><b>Separate ₹2,50,000 paper account and separate positions/journal</b></div></div>", unsafe_allow_html=True)
with right:
    st.markdown("<div class='dashboard-info-card'><div class='session-row'><span>Worker</span><b>" + s2_status + "</b></div><div class='session-row'><span>Last scan</span><b>" + str(strategy2.get("last_scan") or "Not scanned yet") + "</b></div><div class='session-row'><span>Signals</span><b>" + str(int(strategy2.get("last_signal_count", 0) or 0)) + "</b></div><div class='session-row'><span>Capital</span><b>" + money(s2_capital) + "</b></div></div>", unsafe_allow_html=True)
if strategy2.get("last_error"):
    st.error(f"Strategy 2 scan error: {strategy2['last_error']}")

st.subheader("🔒 Separation & Safety")
st.dataframe(pd.DataFrame([
    ("Capital", "₹2,50,000 Strategy 1", "₹2,50,000 Strategy 2", "SEPARATE"),
    ("Positions", "Strategy 1 only", "Strategy 2 only", "SEPARATE"),
    ("Signals", "signals.csv", "strategy2_signals.csv", "SEPARATE"),
    ("Trades", "trades.csv", "strategy2_trades.csv", "SEPARATE"),
    ("Candles", "Completed 1m CLOSE", "Completed 1m CLOSE", "NO FORMING CANDLE"),
    ("Strategy 1 priority", "Highest qualifying GAP %", "—", "NO ATR"),
    ("Strategy 1 SL", "BUY PDH / SELL PDL", "—", "FIXED FOR NOW"),
], columns=["Item", "Strategy 1", "Strategy 2", "Status"]), width="stretch", hide_index=True)

st.caption(f"Dashboard refresh 5s • single paper-bot control cycle 30s • strategy candles 1m completed CLOSE • Updated {now.strftime('%H:%M:%S IST')} • Paper trading only")
render_daily_footer()
