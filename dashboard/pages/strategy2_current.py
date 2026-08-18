"""Strategy 2 single-page command center aligned with Strategy 1."""
from pathlib import Path
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from bot_runner import ensure_bot_running
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.dashboard_utils import build_single_sheet_master_excel
from dashboard.strategy2_data import status, diagnostics, state, gaps, signals, trades, format_price, STARTING_CAPITAL
from market.price_data import PriceData
from strategy.contracts import strategy_metadata

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START, ENTRY_END = "09:45", "14:00"
MIN_RISK, MAX_RISK = 1400.0, 1500.0

st.set_page_config(page_title="NSE Catalyst | Strategy 2", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=5000, key="s2_single_page_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

def age(v):
    try:
        x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        x = x.replace(tzinfo=INDIA_TZ) if x.tzinfo is None else x
        return max(0, int((datetime.now(timezone.utc) - x.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None

def cards(items):
    st.markdown("<div class='metric-grid'>" + "".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items) + "</div>", unsafe_allow_html=True)

def chart(fig, key, height=300):
    fig.update_layout(height=height, margin=dict(l=8,r=8,t=48,b=8), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)

def numeric(df, cols):
    for c in cols:
        if c not in df.columns: df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

try:
    ensure_bot_running()
except Exception:
    pass

s = status() or {}
d = diagnostics() or {}
paper = state() or {}
gap = gaps()
sig = signals()
all_trades = trades()
now = datetime.now(INDIA_TZ)
positions = paper.get("open_positions", {}) or {}
scan_age = age(d.get("timestamp"))
hb = age(s.get("heartbeat"))
worker_ok = bool(s.get("worker_alive")) and hb is not None and hb <= 90
clock = now.strftime("%H:%M")
window = "PREPARE" if clock < ENTRY_START else "ACTIVE" if clock <= ENTRY_END else "CLOSED"
meta = strategy_metadata("STRATEGY_2")

st.title("🔴 Strategy 2")
st.caption(f"{meta['name']} • {meta['version']} • Single-page command center • LIVE LTP entry / SL / target • no candle-close confirmation • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([("WORKER", "🟢 RUNNING" if worker_ok else "🔴 STALE"), ("AVAILABLE CAPITAL", format_price(s.get("available_capital", STARTING_CAPITAL))), ("ENTRY WINDOW", window), ("OPEN POSITIONS", len(positions)), ("REALIZED DAILY P&L", format_price(s.get("daily_pnl", 0))), ("LAST SCAN", f"{scan_age}s ago" if scan_age is not None else "—"), ("EXIT MONITOR", "LIVE / ~5s UI")])
if s.get("last_error"):
    st.error(str(s["last_error"]))

# SAME SCANNER STRUCTURE AS S1
st.subheader("🔎 Live Scanner & Trading")
risk_approved = 0
if not sig.empty and "approved" in sig.columns:
    risk_approved = int(sig["approved"].astype(str).str.lower().isin(["true","1","yes"]).sum())
opening = int(d.get("opening_setup_passed", d.get("buy_candidates", 0) or 0) or 0) + int(d.get("sell_candidates", 0) or 0)
qualified = int(d.get("strategy_setup_passed", d.get("buy_qualified", 0) or 0) or 0) + int(d.get("sell_qualified", 0) or 0)
reference = d.get("reference_data_count", d.get("reference_data", d.get("candidates", 0)))
alignment = d.get("market_alignment_passed", d.get("market_alignment", "—"))
coverage = d.get("market_data_coverage", d.get("coverage", None))
coverage_text = "—" if coverage is None else f"{float(coverage):.0%}"
cards([("STOCKS SCANNED", d.get("stocks_scanned", d.get("candidates", 0))), ("REFERENCE DATA", reference), ("OPENING SETUPS", opening), ("MARKET ALIGNMENT", alignment), ("QUALIFIED", qualified), ("FINAL SIGNALS", d.get("final_signals", d.get("signals", 0))), ("RISK APPROVED", risk_approved), ("1m COVERAGE", coverage_text)])

with st.expander("📋 Scanner Pipeline & Alignment", expanded=False):
    pipeline = pd.DataFrame([
        ("Universe", d.get("stocks_scanned", d.get("candidates", 0)), "NIFTY 500 opening GAP candidates", "DATA"),
        ("Reference", reference, "PDH / PDL / PDC / Open", "DATA"),
        ("Opening setup", opening, "Opening GAP extension / setup", "SETUP"),
        ("Market alignment", alignment, "Strategy 2 alignment gate when supplied by scanner", "GATE"),
        ("Strategy qualified", qualified, "Live price reached required reversal state", "LIVE LTP"),
        ("Final signals", d.get("final_signals", d.get("signals", 0)), "Live entry + risk checks", "ENTRY"),
    ], columns=["Stage", "Count", "Rule / Data", "Type"])
    st.dataframe(pipeline, width="stretch", hide_index=True)

with st.expander("⏳ Waiting / Qualified Stocks", expanded=False):
    waiting_rows = []
    waiting = d.get("waiting", {}) if isinstance(d, dict) else {}
    qualified_data = d.get("qualified", {}) if isinstance(d, dict) else {}
    for state_name, bucket in (("WAITING", waiting), ("QUALIFIED", qualified_data)):
        if isinstance(bucket, dict):
            for side, items in bucket.items():
                if isinstance(items, dict):
                    for symbol, item in items.items():
                        item = item if isinstance(item, dict) else {}
                        waiting_rows.append({"Side": str(side).upper(), "Stock": symbol, "State": item.get("state", state_name), "Open": item.get("today_open", "—"), "PDH": item.get("pdh", "—"), "PDL": item.get("pdl", "—"), "Gap %": item.get("gap_percent", "—"), "Qualified At": item.get("qualified_time", item.get("qualified_at", "—"))})
    if waiting_rows:
        st.dataframe(pd.DataFrame(waiting_rows), width="stretch", hide_index=True, height=340)
    else:
        st.info("No stocks currently waiting for a live state transition.")

with st.expander("🚨 Today's Approved Signals", expanded=False):
    today = sig.copy()
    if not today.empty:
        date_col = "entry_time" if "entry_time" in today.columns else "timestamp" if "timestamp" in today.columns else None
        if date_col:
            z = pd.to_datetime(today[date_col], errors="coerce")
            z = z.dt.tz_localize(INDIA_TZ) if z.dt.tz is None else z.dt.tz_convert(INDIA_TZ)
            today = today.loc[z.dt.date.eq(now.date())]
        if "approved" in today.columns:
            today = today[today["approved"].astype(str).str.lower().isin(["true","1","yes"])]
        cols = [c for c in ["strategy","symbol","signal","entry_time","entry","stop_loss","target","quantity","actual_risk","risk_reward","entry_source","priority_rank"] if c in today.columns]
        if not today.empty and cols:
            st.dataframe(today[cols].tail(25).iloc[::-1], width="stretch", hide_index=True)
        else:
            st.info("No approved signals today.")
    else:
        st.info("No approved signals today.")

with st.expander("📍 Open Paper Positions", expanded=True):
    st.caption("LTP, SL and target are monitored independently of candle close. Entry and exit times are stored in IST.")
    if positions:
        pdx = PriceData(); rows = []
        for symbol, position in positions.items():
            try:
                live = pdx.get_latest_live_price(symbol, max_age_seconds=3); ltp = live.get("Close") if live else None
            except Exception:
                live, ltp = None, None
            entry = position.get("entry"); side = str(position.get("signal", "")).upper(); qty = int(float(position.get("quantity", 0) or 0)); pnl = None
            try:
                if ltp is not None and entry is not None:
                    pnl = ((float(ltp)-float(entry))*qty) if side == "BUY" else ((float(entry)-float(ltp))*qty)
            except Exception:
                pass
            rows.append({"Strategy": "STRATEGY_2", "Stock": symbol, "Side": side, "Entry": format_price(entry), "LTP": format_price(ltp), "Live P&L": format_price(pnl), "SL": format_price(position.get("stop_loss")), "Target": format_price(position.get("target")), "Qty": qty, "Risk": format_price(position.get("actual_risk", position.get("risk"))), "Entry Time": position.get("entry_time", "—"), "Exit Time": position.get("exit_time", "—"), "Price Data": live.get("price_source", "LIVE") if live else "STALE/UNAVAILABLE"})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No open Strategy 2 paper positions.")

# SAME ANALYSIS STRUCTURE AS S1
with st.expander("📊 Analysis — complete before-trade + after-trade analysis", expanded=True):
    closed = all_trades.copy()
    for c in ["pnl","entry","stop_loss","target","quantity","actual_risk","risk","rr","risk_reward","gap_percent"]:
        if c not in closed.columns: closed[c] = 0.0
        closed[c] = pd.to_numeric(closed[c], errors="coerce").fillna(0.0)
    if "status" in closed.columns:
        closed = closed[closed["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if not closed.empty:
        closed = closed.reset_index(drop=True)
        closed["Trade #"] = range(1, len(closed)+1)
        closed["Result"] = closed["pnl"].map(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
        closed["Cumulative P&L"] = closed["pnl"].cumsum()
        closed["Peak"] = closed["Cumulative P&L"].cummax()
        closed["Drawdown"] = closed["Cumulative P&L"] - closed["Peak"]
    wins = int((closed["pnl"] > 0).sum()) if not closed.empty else 0
    losses = int((closed["pnl"] < 0).sum()) if not closed.empty else 0
    net = float(closed["pnl"].sum()) if not closed.empty else 0.0
    gp = float(closed.loc[closed["pnl"] > 0, "pnl"].sum()) if not closed.empty else 0.0
    gl = abs(float(closed.loc[closed["pnl"] < 0, "pnl"].sum())) if not closed.empty else 0.0
    pf = gp / gl if gl else 0.0
    wr = wins / len(closed) * 100 if not closed.empty else 0.0
    dd = abs(float(closed["Drawdown"].min())) if not closed.empty else 0.0
    cards([("Decision Records", len(sig)), ("Closed Trades", len(closed)), ("Wins / Losses", f"{wins} / {losses}"), ("Net P&L", format_price(net)), ("Equity", format_price(STARTING_CAPITAL + net)), ("Win Rate", f"{wr:.1f}%"), ("Profit Factor", f"{pf:.2f}"), ("Max Drawdown", format_price(dd))])

    with st.expander("🟢 Before Trade — setup & decision analysis", expanded=False):
        st.caption("What the system knew before entry. No post-entry values are used here.")
        cols = [c for c in ["timestamp","symbol","signal","today_open","pdh","pdl","gap_percent","entry","stop_loss","target","quantity","actual_risk","risk_reward","approved","reason"] if c in sig.columns]
        before = sig[cols].tail(500).iloc[::-1] if cols else sig.tail(500).iloc[::-1]
        if not before.empty: st.dataframe(before, width="stretch", hide_index=True, height=420)
        else: st.info("No pre-trade decision records yet.")
        if not sig.empty:
            if "approved" in sig.columns:
                outcome = sig["approved"].astype(str).str.lower().isin(["true","1","yes"]).map({True:"Approved",False:"Rejected / Watch"}).value_counts().rename_axis("Outcome").reset_index(name="Decisions")
                chart(px.bar(outcome, x="Outcome", y="Decisions", text="Decisions", title="Pre-Trade Decision Outcome"), "s2_before_outcome")
            if "signal" in sig.columns:
                side = sig["signal"].astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions")
                chart(px.bar(side, x="Signal", y="Decisions", text="Decisions", title="Pre-Trade BUY vs SELL"), "s2_before_side")
            if "gap_percent" in sig.columns and "actual_risk" in sig.columns:
                pre = sig.copy(); pre["gap_percent"] = pd.to_numeric(pre["gap_percent"], errors="coerce"); pre["actual_risk"] = pd.to_numeric(pre["actual_risk"], errors="coerce")
                chart(px.scatter(pre, x="gap_percent", y="actual_risk", hover_data=[c for c in ["symbol","approved","reason"] if c in pre.columns], title="Pre-Trade GAP vs Actual Risk"), "s2_before_gap_risk")

    with st.expander("⚡ Entry Quality — what happened at the trigger", expanded=False):
        cols = [c for c in ["strategy","symbol","signal","entry","entry_time","market_entry_time","trigger_entry_time","today_open","pdh","pdl","gap_percent","stop_loss","target","quantity","actual_risk","risk_reward","entry_source","reason"] if c in closed.columns]
        view = closed[cols].tail(500).iloc[::-1] if cols and not closed.empty else pd.DataFrame()
        if not view.empty: st.dataframe(view, width="stretch", hide_index=True, height=360)
        else: st.info("No completed entry records yet.")

    with st.expander("🔴 After Trade — exit, P&L and outcome analysis", expanded=True):
        if closed.empty:
            st.info("No completed Strategy 2 trades yet. Post-trade analysis will populate automatically after exits.")
        else:
            cols = [c for c in ["Trade #","symbol","signal","entry","entry_time","exit","exit_price","exit_time","stop_loss","target","quantity","actual_risk","pnl","exit_reason","status"] if c in closed.columns]
            st.dataframe(closed[cols].tail(500).iloc[::-1], width="stretch", hide_index=True, height=430)
            a,b = st.columns(2)
            with a: chart(px.line(closed, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L After Trades"), "s2_after_cum")
            with b: chart(px.area(closed, x="Trade #", y="Drawdown", title="Drawdown After Trades"), "s2_after_dd")
            a,b = st.columns(2)
            with a: chart(px.histogram(closed, x="pnl", nbins=14, title="Trade P&L Distribution"), "s2_after_pnl")
            with b: chart(px.bar(closed.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "s2_after_result")
            if "exit_reason" in closed.columns:
                exits = closed["exit_reason"].fillna("Unknown").astype(str).value_counts().rename_axis("Exit Reason").reset_index(name="Trades")
                chart(px.bar(exits, x="Exit Reason", y="Trades", text="Trades", title="Exit Reasons"), "s2_after_exit_reason")

    with st.expander("📈 Performance & Pattern Analysis", expanded=False):
        if not closed.empty and "symbol" in closed.columns:
            stock = closed.groupby("symbol", as_index=False).agg(Trades=("symbol","size"), PnL=("pnl","sum"), Win_Rate=("pnl", lambda x:(x>0).mean()*100)).sort_values("PnL", ascending=False)
            a,b = st.columns(2)
            with a: chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "s2_perf_stocks", 340)
            with b: st.dataframe(stock, width="stretch", hide_index=True, height=300)
        else:
            st.info("Performance patterns will appear after completed trades.")

    with st.expander("📋 Decision Records", expanded=False):
        cols = [c for c in ["timestamp","symbol","signal","gap_percent","entry","stop_loss","target","quantity","actual_risk","risk_reward","approved","reason"] if c in sig.columns]
        st.dataframe(sig[cols].tail(500).iloc[::-1] if cols else sig.tail(500).iloc[::-1], width="stretch", hide_index=True, height=400)

    with st.expander("📋 Trade Taken Details — Entry / Exit / P&L", expanded=False):
        cols = [c for c in ["strategy","symbol","signal","entry","entry_time","market_entry_time","trigger_entry_time","exit","exit_price","exit_time","stop_loss","target","quantity","actual_risk","pnl","exit_reason","status"] if c in closed.columns]
        st.dataframe(closed[cols].tail(500).iloc[::-1] if cols else closed.tail(500).iloc[::-1], width="stretch", hide_index=True, height=450)

    with st.expander("⚡ Authoritative Strategy Rules", expanded=False):
        rules = list(meta.get("rules", []))
        rules += [("Risk", "₹1,400–₹1,500 intended actual risk"), ("Entry window", "09:45–14:00 IST"), ("Monitoring", "LIVE LTP • no candle-close confirmation"), ("Square-off", "15:00 IST")]
        st.dataframe(pd.DataFrame(rules, columns=["Rule","Definition"]), width="stretch", hide_index=True)

with st.expander("⬇️ Downloads — single-sheet master", expanded=False):
    try:
        master_bytes = build_single_sheet_master_excel(all_trades, sig, gap)
        st.caption("One workbook • one worksheet: ALL DATA • trades + signals + premarket gap board • S1/S2 kept in the Strategy column.")
        st.download_button("⬇️ DOWNLOAD ALL STRATEGIES — SINGLE SHEET EXCEL", data=master_bytes, file_name="NSE_CATALYST_ALL_STRATEGIES_SINGLE_SHEET.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    except Exception as error:
        st.error(f"Single-sheet master unavailable: {type(error).__name__}: {error}")

st.caption(f"Heartbeat: {s.get('heartbeat','—')} • Last scan: {d.get('timestamp','—')} • Strategy 2 single-page mode • UI refresh: 5s")
render_daily_footer()
