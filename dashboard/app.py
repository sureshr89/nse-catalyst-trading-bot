"""
Trading Dashboard
"""

from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# LOCAL IMPORTS (No "dashboard.")
from dashboard_utils import (
    load_csv,
    format_money,
    format_percent,
    last_trades,
)

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
)

# ----------------------------------------------------------

st.set_page_config(
    page_title="NSE Catalyst Trading Bot",
    page_icon="📈",
    layout="wide"
)

# 1. Auto Refresh (Every 5 seconds)
st_autorefresh(
    interval=5000,
    key="dashboard_refresh"
)

st.title("📈 NSE Catalyst Trading Bot Dashboard")

# 2. Detailed Market Status Card based on current time and weekday
now = datetime.now()
current_time = now.time()
market_open_time = datetime.strptime(MARKET_OPEN, "%H:%M").time()
market_close_time = datetime.strptime(MARKET_CLOSE, "%H:%M").time()

if now.weekday() >= 5:
    st.warning("🟡 Weekend - Market Closed")
elif current_time < market_open_time:
    st.info("🟡 Waiting for Market Open")
elif current_time > market_close_time:
    st.error("🔴 Market Closed")
else:
    st.success("🟢 Paper Trading Running")

# ----------------------------------------------------------
# Load trades safely with a friendly message if missing
# ----------------------------------------------------------

try:
    trades = load_csv("outputs/trades.csv")
except Exception:
    trades = None

if trades is None or trades.empty:
    st.info("No trades available yet.")
    metrics = {
        "total_trades": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "profit_factor": 0.0,
        "available_capital": TOTAL_CAPITAL,
        "used_capital": 0.0,
        "current_equity": TOTAL_CAPITAL,
        "winning_trades": 0,
        "losing_trades": 0,
        "open_positions": 0,
        "max_drawdown": 0.0,
    }
else:
    metrics = calculate_metrics(trades)

# ----------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Trades",
    metrics["total_trades"]
)

c2.metric(
    "Win Rate",
    format_percent(metrics["win_rate"])
)

c3.metric(
    "Total P&L",
    format_money(metrics["total_pnl"])
)

c4.metric(
    "Profit Factor",
    metrics["profit_factor"]
)

# ----------------------------------------------------------

c1, c2, c3 = st.columns(3)

c1.metric(
    "Available Capital",
    format_money(metrics["available_capital"])
)

c2.metric(
    "Used Capital",
    format_money(metrics["used_capital"])
)

c3.metric(
    "Current Equity",
    format_money(metrics["current_equity"])
)

# ----------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Trades",
        "Charts",
        "Capital",
        "Performance",
    ]
)

# ----------------------------------------------------------

with tab1:

    st.subheader("Latest Trades")

    if trades is not None and not trades.empty:
        st.dataframe(
            last_trades(trades, 20),
            use_container_width=True,
        )
    else:
        st.info("No trades to display.")

# ----------------------------------------------------------

with tab2:

    if trades is not None and not trades.empty:
        fig = equity_curve(trades)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True
            )

        fig = pnl_chart(trades)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True
            )
    else:
        st.info("No chart data available yet.")

# ----------------------------------------------------------

with tab3:

    fig = capital_chart(metrics)

    if fig is not None:
        st.plotly_chart(
            fig,
            use_container_width=True
        )

# ----------------------------------------------------------

with tab4:

    if trades is not None and not trades.empty:
        fig = win_loss_chart(trades)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True
            )

        fig = industry_chart(trades)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True
            )

        fig = monthly_pnl_chart(trades)
        if fig is not None:
            st.plotly_chart(
                fig,
                use_container_width=True
            )
    else:
        st.info("No performance metrics available yet.")

# ----------------------------------------------------------

st.sidebar.title("Trading Summary")

st.sidebar.write(
    "Total Trades:",
    metrics["total_trades"]
)

st.sidebar.write(
    "Winning Trades:",
    metrics["winning_trades"]
)

st.sidebar.write(
    "Losing Trades:",
    metrics["losing_trades"]
)

st.sidebar.write(
    "Open Positions:",
    metrics["open_positions"]
)

st.sidebar.write(
    "Profit Factor:",
    metrics["profit_factor"]
)

st.sidebar.write(
    "Max Drawdown:",
    format_money(metrics["max_drawdown"])
)

# 3. Last Scan Time in Sidebar
st.sidebar.write(
    "Last Refresh:",
    datetime.now().strftime("%H:%M:%S")
)