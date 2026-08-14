import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from worker_service import ensure_worker_process
from market.price_data import PriceData
from data.stock_universe import StockUniverse
from data.sector_store import SectorStore

ROOT = Path(__file__).resolve().parents[2]
INDIA_TZ = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst | Current Trading", page_icon="📌", layout="wide")
st_autorefresh(interval=5000, key="current_live")
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


def candle_pct(candle):
    if not candle:
        return None
    try:
        op = float(candle["Open"])
        cl = float(candle["Close"])
        return ((cl - op) / op * 100.0) if op else None
    except Exception:
        return None


def candle_label(pct):
    if pct is None:
        return "—"
    return f"{pct:+.2f}%"


@st.cache_data(ttl=30, show_spinner=False)
def live_alignment_for_positions(symbols, trigger_times):
    """Fetch only the small set needed for the live traded-position table.

    Stock and NIFTY 500 values are the latest completed 1-minute candle. Sector
    percentage is the equal-weight average 1-minute return of the sector's
    NIFTY 500 constituents. This is display/monitoring data; it does not alter
    the entry engine.
    """
    symbols = [str(s).upper().replace(".NS", "") for s in symbols if str(s).strip()]
    if not symbols:
        return pd.DataFrame()
    price = PriceData()
    universe = StockUniverse().get_dataframe(refresh=False)
    sectors = SectorStore(universe).prepare(force=False)
    latest_nifty = price.get_index_1m("^CRSLDX")
    nifty = None if latest_nifty.empty else latest_nifty.iloc[-1].to_dict()
    rows = []
    stock_data = price.get_multi_1m(symbols)
    for symbol in symbols:
        candle = None
        df = stock_data.get(symbol, pd.DataFrame())
        if df is not None and not df.empty:
            candle = df.iloc[-1].to_dict()
        sector = "UNKNOWN"
        if not sectors.empty:
            match = sectors[sectors["Symbol"].astype(str).str.upper().eq(symbol)]
            if not match.empty:
                sector = str(match.iloc[0].get("Sector", "UNKNOWN"))
        sector_members = []
        if not sectors.empty and sector != "UNKNOWN":
            sector_members = sectors[sectors["Sector"].astype(str).eq(sector)]["Symbol"].astype(str).str.upper().tolist()
        member_data = price.get_multi_1m(sector_members) if sector_members else {}
        member_pcts = []
        for member in sector_members:
            mdf = member_data.get(member, pd.DataFrame())
            if mdf is None or mdf.empty:
                continue
            pct = candle_pct(mdf.iloc[-1].to_dict())
            if pct is not None:
                member_pcts.append(pct)
        sector_pct = sum(member_pcts) / len(member_pcts) if member_pcts else None
        stock_pct = candle_pct(candle)
        nifty_pct = candle_pct(nifty)
        rows.append({
            "Stock": symbol,
            "Sector": sector,
            "NIFTY 500 1m %": candle_label(nifty_pct),
            "Sector 1m %": candle_label(sector_pct),
            "Stock 1m %": candle_label(stock_pct),
            "NIFTY 500": "GREEN" if nifty_pct is not None and nifty_pct > 0 else "RED" if nifty_pct is not None and nifty_pct < 0 else "NEUTRAL",
            "Sector": sector,
            "Stock Candle": "GREEN" if stock_pct is not None and stock_pct > 0 else "RED" if stock_pct is not None and stock_pct < 0 else "NEUTRAL",
            "Candle Time": candle.get("Datetime") if candle else (nifty.get("Datetime") if nifty else "—"),
        })
    return pd.DataFrame(rows)


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
st.caption("NIFTY 500 • PDH/PDL-relative gap preparation → level break → today's Open 1-minute reversal")
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

st.subheader("Opening Gap Board — PDH/PDL based, ready before 09:45")
if not gaps.empty and "GapType" in gaps.columns:
    g = gaps.copy()
    g["GapPercent"] = pd.to_numeric(g.get("GapPercent"), errors="coerce")
    ups = g[g["GapType"].eq("GAP_UP_PDH")].sort_values("GapPercent", ascending=False)
    downs = g[g["GapType"].eq("GAP_DOWN_PDL")].sort_values("GapPercent")
    a, b = st.columns(2)
    with a:
        st.markdown("**🟢 Gap Ups — Open > PDH**")
        st.dataframe(ups[[c for c in ["Symbol","TodayOpen","PDH","Gap","GapPercent","PreviousClose","PDL"] if c in ups.columns]].head(25), width="stretch", hide_index=True, height=320)
    with b:
        st.markdown("**🔴 Gap Downs — Open < PDL**")
        st.dataframe(downs[[c for c in ["Symbol","TodayOpen","PDL","Gap","GapPercent","PreviousClose","PDH"] if c in downs.columns]].head(25), width="stretch", hide_index=True, height=320)
else:
    st.info("The PDH/PDL opening gap board is prepared automatically after the 09:15 market open and before the 09:45 entry window.")

st.subheader("Open Positions")
if pos:
    rows = []
    for symbol, p in pos.items():
        rows.append({"Stock": symbol, "Side": p.get("signal", ""), "Entry": p.get("entry"), "SL": p.get("stop_loss"), "Target": p.get("target"), "Qty": p.get("quantity"), "Risk": p.get("actual_risk", p.get("risk")), "R:R": p.get("rr", 1.25), "Entry Time": p.get("entry_time"), "Trigger Time": p.get("trigger_entry_time", "—"), "Setup": p.get("setup_type", "NIFTY_500_PDH_PDL_OPEN_REVERSAL"), "Gap % vs PDH/PDL": p.get("gap_percent", "—"), "PDH": p.get("pdh", "—"), "PDL": p.get("pdl", "—"), "Open": p.get("today_open", "—")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Live Alignment — Latest Completed 1-Minute Candle")
    st.caption("Percentages are candle Open → Close. NIFTY 500, sector and stock are shown for the currently traded stocks. Data refreshes every 5 seconds; market data is cached for 30 seconds to avoid slowing the bot.")
    try:
        live_df = live_alignment_for_positions(list(pos.keys()), [p.get("entry_time") for p in pos.values()])
        if not live_df.empty:
            st.dataframe(live_df[["Stock", "Sector", "NIFTY 500 1m %", "Sector 1m %", "Stock 1m %", "NIFTY 500", "Stock Candle", "Candle Time"]], width="stretch", hide_index=True)
        else:
            st.info("Live alignment will appear when completed 1-minute candles are available.")
    except Exception as error:
        st.warning(f"Live alignment temporarily unavailable: {type(error).__name__}: {error}")
else:
    st.info("No open paper positions.")

st.subheader("Scanner Filter Breakdown")
if isinstance(diag, dict) and diag:
    grid([
        ("NIFTY 500 Scanned", diag.get("stocks_scanned", 0)),
        ("Gap Data Ready", diag.get("gap_data_count", 0)),
        ("Gap Ups > PDH", diag.get("gap_up_count", 0)),
        ("Gap Downs < PDL", diag.get("gap_down_count", 0)),
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
    grid([("Stock", t.get("symbol", "—")), ("Side", t.get("signal", "—")), ("Entry", t.get("entry", "—")), ("Exit", t.get("exit_price", "—")), ("P&L", f"₹{float(t.get('pnl', 0) or 0):,.2f}"), ("Exit Reason", t.get("exit_reason", "—")), ("PDH", t.get("pdh", "—")), ("PDL", t.get("pdl", "—")), ("Open", t.get("today_open", "—")), ("Gap % vs PDH/PDL", t.get("gap_percent", "—")), ("Setup", t.get("setup_type", "—")), ("Sector", t.get("sector", "—")), ("Market", t.get("market_direction", "—"))])
else:
    st.info("No closed paper trade yet.")

st.subheader("Recent Trades")
if not trades.empty:
    st.dataframe(trades.iloc[::-1].head(30), width="stretch", hide_index=True)
else:
    st.info("No trades recorded yet.")
render_daily_footer()
