"""NSE Catalyst Trading Bot Dashboard."""

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from bot_runner import start_bot, get_status
from dashboard_utils import load_csv, format_money, format_percent, last_trades
from metrics import calculate_metrics
from charts import (
    equity_curve,
    pnl_chart,
    win_loss_chart,
    industry_chart,
    capital_chart,
    monthly_pnl_chart,
)
from config.settings import (
    MARKET_OPEN,
    MARKET_CLOSE,
    TOTAL_CAPITAL,
    PAPER_TRADING,
    LIVE_TRADING,
    TRADING_START,
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    SCAN_INTERVAL_SECONDS,
)

INDIA_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="NSE Catalyst Trading Bot",
    page_icon="📈",
    layout="wide",
)

st_autorefresh(interval=5000, key="dashboard_refresh")

try:
    start_bot()
except Exception:
    pass

bot_status = get_status()

now = datetime.now(INDIA_TZ)
current_time = now.time()
market_open_time = datetime.strptime(MARKET_OPEN, "%H:%M").time()
market_close_time = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
trading_start_time = datetime.strptime(TRADING_START, "%H:%M").time()
last_entry_time = datetime.strptime(LAST_ENTRY_TIME, "%H:%M").time()
square_off_time = datetime.strptime(SQUARE_OFF_TIME, "%H:%M").time()

# The dashboard must derive the session state from the real IST clock.
# This prevents a stale bot_status.json from making a closed-market session
# appear to be RUNNING or from showing a fake scanner timestamp.
market_session_active = (
    now.weekday() < 5
    and current_time >= trading_start_time
    and current_time < square_off_time
)
scanner_window_active = (
    now.weekday() < 5
    and current_time >= trading_start_time
    and current_time <= last_entry_time
)

raw_status = bot_status.get("status", "UNKNOWN")
error_text = bot_status.get("error")

if error_text:
    status = "ERROR"
elif market_session_active:
    status = "RUNNING" if raw_status != "ERROR" else "ERROR"
else:
    status = "WAITING"

scanner_status = bot_status.get("scanner_status", "IDLE") if scanner_window_active else "IDLE"
last_scan = bot_status.get("last_scan") if scanner_window_active else None
last_cycle = bot_status.get("last_cycle") if market_session_active else None

st.title("📈 NSE Catalyst Trading Bot Dashboard")

if status == "RUNNING":
    st.success("🟢 PAPER BOT RUNNING")
elif status == "ERROR":
    st.error("🔴 BOT ERROR")
else:
    st.warning("🟡 WAITING FOR MARKET SESSION")

s1, s2, s3, s4 = st.columns(4)
s1.metric("India Time", now.strftime("%H:%M:%S"))
s2.metric("Bot Status", status)
s3.metric("Last Bot Cycle", str(last_cycle or "Not during session"))
s4.metric("Last Scanner Run", str(last_scan or "Not during scanner window"))

if error_text:
    st.error(f"Bot error: {error_text}")

with st.expander("Bot / Strategy Status", expanded=True):
    a, b, c, d = st.columns(4)
    a.write(f"**Paper Trading:** {PAPER_TRADING}")
    b.write(f"**Live Trading:** {LIVE_TRADING}")
    c.write(f"**Scanner:** {scanner_status}")
    d.write(f"**Scan Interval:** {SCAN_INTERVAL_SECONDS}s")
    st.write(
        f"**Entry window:** {TRADING_START} → {LAST_ENTRY_TIME} IST  |  "
        f"**Square-off:** {SQUARE_OFF_TIME} IST"
    )

if now.weekday() >= 5:
    st.warning("🟡 Weekend - Market Closed")
elif current_time < market_open_time:
    st.info("🟡 Waiting for Market Open")
elif current_time >= market_close_time:
    st.error("🔴 Market Closed")
elif current_time > last_entry_time:
    st.info("🟡 Entry window closed - existing positions only")
else:
    st.success("🟢 Indian market session")

try:
    trades = load_csv("outputs/trades.csv")
except Exception:
    trades = None

if trades is None or trades.empty:
    if market_session_active:
        st.info("No completed trades yet. The bot is running and waiting for valid setups.")
    elif status == "WAITING":
        st.info("No completed trades yet. Bot is waiting for the next Indian market session.")
    else:
        st.info("No trades available yet.")

    metrics = {
        "total_trades": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "profit_factor": 0.0,
        "available_capital": bot_status.get("available_capital", TOTAL_CAPITAL),
        "used_capital": bot_status.get("used_capital", 0.0),
        "current_equity": bot_status.get("available_capital", TOTAL_CAPITAL),
        "winning_trades": 0,
        "losing_trades": 0,
        "open_positions": bot_status.get("open_positions", 0),
        "max_drawdown": 0.0,
    }
else:
    metrics = calculate_metrics(trades)

if market_session_active:
    metrics["open_positions"] = bot_status.get("open_positions", metrics.get("open_positions", 0))
    metrics["available_capital"] = bot_status.get("available_capital", metrics.get("available_capital", TOTAL_CAPITAL))
    metrics["used_capital"] = bot_status.get("used_capital", metrics.get("used_capital", 0.0))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", metrics["total_trades"])
c2.metric("Win Rate", format_percent(metrics["win_rate"]))
c3.metric("Total P&L", format_money(metrics["total_pnl"]))
c4.metric("Profit Factor", metrics["profit_factor"])

c1, c2, c3 = st.columns(3)
c1.metric("Available Capital", format_money(metrics["available_capital"]))
c2.metric("Used Capital", format_money(metrics["used_capital"]))
c3.metric("Current Equity", format_money(metrics["current_equity"]))

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Trades", "Signals", "Charts", "Capital", "Performance"])

with tab1:
    st.subheader("Latest Trades")
    if trades is not None and not trades.empty:
        st.dataframe(last_trades(trades, 20), use_container_width=True)
    else:
        st.info("No completed trades to display.")

with tab2:
    st.subheader("Latest Scanner Signals")
    try:
        signals = load_csv("outputs/signals.csv")
    except Exception:
        signals = None
    if signals is not None and not signals.empty:
        st.dataframe(signals.tail(30).iloc[::-1], use_container_width=True)
    else:
        st.info("No scanner signals recorded yet.")

with tab3:
    if trades is not None and not trades.empty:
        fig = equity_curve(trades)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        fig = pnl_chart(trades)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No chart data available yet.")

with tab4:
    fig = capital_chart(metrics)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    if trades is not None and not trades.empty:
        fig = win_loss_chart(trades)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        fig = industry_chart(trades)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        fig = monthly_pnl_chart(trades)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No performance metrics available yet.")

st.sidebar.title("Trading Summary")
st.sidebar.write(f"**Bot:** {status}")
st.sidebar.write(f"**India Time:** {now.strftime('%H:%M:%S IST')}")
st.sidebar.write(f"**Last Cycle:** {last_cycle or 'Not during session'}")
st.sidebar.write(f"**Last Scanner:** {last_scan or 'Not during scanner window'}")
st.sidebar.write(f"**Scanner:** {scanner_status}")
st.sidebar.write(f"**Total Trades:** {metrics['total_trades']}")
st.sidebar.write(f"**Winning Trades:** {metrics['winning_trades']}")
st.sidebar.write(f"**Losing Trades:** {metrics['losing_trades']}")
st.sidebar.write(f"**Open Positions:** {metrics['open_positions']}")
st.sidebar.write(f"**Profit Factor:** {metrics['profit_factor']}")
st.sidebar.write(f"**Max Drawdown:** {format_money(metrics['max_drawdown'])}")
st.sidebar.write(f"**Daily P&L:** {format_money(bot_status.get('daily_pnl', 0.0))}")
st.sidebar.write(f"**Dashboard Refresh:** {now.strftime('%H:%M:%S IST')}")
