"""Strategy 1 single-page command center with live trading and deep before/after-trade analysis."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
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
STARTING_CAPITAL = 250000.0
MIN_RISK, MAX_RISK = 1400.0, 1500.0

st.set_page_config(page_title="NSE Catalyst | Strategy 1", page_icon="🔵", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=5000, key="s1_single_page_live")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


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


def chart(fig, key, height=300):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=48, b=8), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


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
trades = read(ROOT / "outputs/trades.csv", "csv")
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
st.title("🔵 Strategy 1")
st.caption(f"{meta['name']} • {meta['version']} • Single-page command center • LIVE LTP entry / SL / target • no candle-close confirmation • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([
    ("WORKER", "🟢 RUNNING" if worker_ok else "🔴 STALE"), ("NIFTY 500", money(nifty)), ("NIFTY CHANGE", pct(nifty_change)),
    ("ENTRY WINDOW", window), ("OPEN POSITIONS", len(positions)), ("REALIZED DAILY P&L", money(status.get("daily_pnl", status.get("session_pnl", 0)))),
    ("LAST SCAN", f"{scan_age}s ago" if scan_age is not None else "—"), ("EXIT MONITOR", "LIVE / ~5s UI"),
])
alignment_panel(nifty, nifty_change, NIFTY500_MIN_CHANGE_PCT, index_age, scan_age)

if status.get("error") or status.get("last_scan_error"):
    st.error(str(status.get("error") or status.get("last_scan_error")))

st.subheader("🔎 Live Scanner & Trading")
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
    st.warning(f"Scanner safety gate: 1-minute coverage {coverage:.0%} is below required {required:.0%}.")

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
                if ltp is not None and entry is not None: pnl = ((float(ltp) - float(entry)) * qty) if side == "BUY" else ((float(entry) - float(ltp)) * qty)
            except Exception: pass
            rows.append({"Strategy": position.get("strategy", "STRATEGY_1"), "Stock": symbol, "Side": side, "Entry": money(entry), "LTP": money(ltp), "Live P&L": money(pnl), "SL": money(position.get("stop_loss")), "Target": money(position.get("target")), "Qty": qty, "Risk": money(position.get("actual_risk", position.get("risk"))), "Entry Time": position.get("entry_time", "—"), "Exit Time": position.get("exit_time", "—"), "Price Data": live.get("price_source", "LIVE") if live else "STALE/UNAVAILABLE"})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else: st.info("No open Strategy 1 paper positions.")

# ---------------- DEEP ANALYSIS ----------------
with st.expander("📊 Analysis — complete before-trade + after-trade analysis", expanded=True):
    closed = trades.copy()
    if not closed.empty and "strategy" in closed.columns:
        closed = closed[closed["strategy"].astype(str).str.upper().isin(["STRATEGY_1", "S1", "OPEN_RETURN"])].copy()
    for c in ["pnl", "entry", "stop_loss", "target", "quantity", "actual_risk", "risk", "rr", "risk_reward", "gap_percent"]:
        if c not in closed.columns: closed[c] = 0.0
        closed[c] = pd.to_numeric(closed[c], errors="coerce").fillna(0.0)
    if "status" in closed.columns:
        closed = closed[closed["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if not closed.empty:
        closed = closed.reset_index(drop=True)
        closed["Trade #"] = range(1, len(closed) + 1)
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
    win_rate = wins / len(closed) * 100 if not closed.empty else 0.0
    max_dd = abs(float(closed["Drawdown"].min())) if not closed.empty else 0.0
    cards([("Decision Records", len(signals)), ("Closed Trades", len(closed)), ("Wins / Losses", f"{wins} / {losses}"), ("Net P&L", money(net)), ("Equity", money(STARTING_CAPITAL + net)), ("Win Rate", f"{win_rate:.1f}%"), ("Profit Factor", f"{pf:.2f}"), ("Max Drawdown", money(max_dd))])

    with st.expander("🟢 Before Trade — setup & decision analysis", expanded=True):
        st.caption("What the system knew and why the trade was or was not allowed before entry. No post-entry values are used in this section.")
        before_cols = [c for c in ["timestamp","symbol","signal","today_open","open","pdh","pdl","pdc","gap_percent","nifty500_change_pct","market_alignment","opening_setup","pdh_breached","pdl_breached","qualified_time","entry","stop_loss","target","quantity","actual_risk","risk_reward","approved","reason"] if c in signals.columns]
        before = signals[before_cols].tail(500).iloc[::-1].copy() if before_cols else signals.tail(500).iloc[::-1].copy()
        if not before.empty:
            st.dataframe(before, width="stretch", hide_index=True, height=420)
        else:
            st.info("No pre-trade decision records yet.")
        if not signals.empty:
            charts = []
            if "approved" in signals.columns:
                outcome = signals["approved"].astype(str).str.lower().isin(["true","1","yes"]).map({True:"Approved",False:"Rejected / Watch"}).value_counts().rename_axis("Outcome").reset_index(name="Decisions")
                charts.append((outcome, "bar", "Outcome"))
            if "signal" in signals.columns:
                side = signals["signal"].astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions")
                charts.append((side, "bar", "Side"))
            a,b = st.columns(2)
            if len(charts) > 0:
                with a: chart(px.bar(charts[0][0], x=charts[0][0].columns[0], y="Decisions", text="Decisions", title="Pre-Trade Decision Outcome"), "s1_before_outcome")
            if len(charts) > 1:
                with b: chart(px.bar(charts[1][0], x=charts[1][0].columns[0], y="Decisions", text="Decisions", title="Pre-Trade BUY vs SELL"), "s1_before_side")
            if "gap_percent" in signals.columns and "actual_risk" in signals.columns:
                pre = signals.copy()
                pre["gap_percent"] = pd.to_numeric(pre["gap_percent"], errors="coerce")
                pre["actual_risk"] = pd.to_numeric(pre["actual_risk"], errors="coerce")
                chart(px.scatter(pre, x="gap_percent", y="actual_risk", color="signal" if "signal" in pre.columns else None, hover_data=[c for c in ["symbol","approved","reason"] if c in pre.columns], title="Pre-Trade GAP vs Actual Risk"), "s1_before_gap_risk")

    with st.expander("⚡ Entry Quality — what happened at the trigger", expanded=False):
        entry_cols = [c for c in ["strategy","symbol","signal","entry","entry_time","market_entry_time","trigger_entry_time","today_open","pdh","pdl","gap_percent","stop_loss","target","quantity","actual_risk","risk_reward","entry_source","reason"] if c in closed.columns]
        entry_view = closed[entry_cols].tail(500).iloc[::-1] if entry_cols and not closed.empty else pd.DataFrame()
        if not entry_view.empty: st.dataframe(entry_view, width="stretch", hide_index=True, height=360)
        else: st.info("No completed entry records yet.")

    with st.expander("🔴 After Trade — exit, P&L and outcome analysis", expanded=True):
        if closed.empty:
            st.info("No completed S1 trades yet. Post-trade analysis will populate automatically after exits.")
        else:
            after_cols = [c for c in ["Trade #","symbol","signal","entry","entry_time","exit","exit_price","exit_time","stop_loss","target","quantity","actual_risk","pnl","exit_reason","status"] if c in closed.columns]
            st.dataframe(closed[after_cols].tail(500).iloc[::-1], width="stretch", hide_index=True, height=430)
            a,b = st.columns(2)
            with a: chart(px.line(closed, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative P&L After Trades"), "s1_after_cum")
            with b: chart(px.area(closed, x="Trade #", y="Drawdown", title="Drawdown After Trades"), "s1_after_dd")
            a,b = st.columns(2)
            with a: chart(px.histogram(closed, x="pnl", nbins=14, title="Trade P&L Distribution"), "s1_after_pnl")
            with b: chart(px.bar(closed.groupby("Result", as_index=False)["pnl"].sum(), x="Result", y="pnl", text="pnl", title="P&L by Outcome"), "s1_after_result")
            if "exit_reason" in closed.columns:
                exits = closed["exit_reason"].fillna("Unknown").astype(str).value_counts().rename_axis("Exit Reason").reset_index(name="Trades")
                chart(px.bar(exits, x="Exit Reason", y="Trades", text="Trades", title="Exit Reasons"), "s1_after_exit_reason")

    with st.expander("📈 Performance & Pattern Analysis", expanded=False):
        if not closed.empty:
            if "symbol" in closed.columns:
                stock = closed.groupby("symbol", as_index=False).agg(Trades=("symbol","size"), PnL=("pnl","sum"), Win_Rate=("pnl",lambda x:(x>0).mean()*100)).sort_values("PnL", ascending=False)
                a,b = st.columns(2)
                with a: chart(px.bar(stock.head(20), x="symbol", y="PnL", text="Trades", title="Stocks by P&L"), "s1_perf_stocks", 340)
                with b: st.dataframe(stock, width="stretch", hide_index=True, height=300)
            if "gap_percent" in closed.columns:
                gap = closed.copy(); gap["Gap Magnitude %"] = gap["gap_percent"].abs()
                chart(px.scatter(gap, x="Gap Magnitude %", y="pnl", hover_data=[c for c in ["symbol","signal"] if c in gap.columns], title="GAP Magnitude vs P&L"), "s1_perf_gap")
            riskcol = "actual_risk" if "actual_risk" in closed.columns and closed["actual_risk"].abs().sum() else "risk"
            if riskcol in closed.columns:
                chart(px.scatter(closed, x=riskcol, y="pnl", hover_data=[c for c in ["symbol","signal","quantity","exit_reason"] if c in closed.columns], title="Risk vs P&L"), "s1_perf_risk")
        else:
            st.info("Performance patterns will appear after completed trades.")

    with st.expander("📋 Decision Records", expanded=False):
        cols = [c for c in ["timestamp","symbol","signal","gap_percent","entry","stop_loss","target","quantity","actual_risk","risk_reward","approved","reason"] if c in signals.columns]
        st.dataframe(signals[cols].tail(500).iloc[::-1] if cols else signals.tail(500).iloc[::-1], width="stretch", hide_index=True, height=400)

    with st.expander("📋 Trade Taken Details — Entry / Exit / P&L", expanded=False):
        cols = [c for c in ["strategy","symbol","signal","entry","entry_time","market_entry_time","trigger_entry_time","exit","exit_price","exit_time","stop_loss","target","quantity","actual_risk","pnl","exit_reason","status"] if c in closed.columns]
        st.dataframe(closed[cols].tail(500).iloc[::-1] if cols else closed.tail(500).iloc[::-1], width="stretch", hide_index=True, height=450)

    with st.expander("⚡ Authoritative Strategy Rules", expanded=False):
        st.dataframe(pd.DataFrame(list(meta["rules"]) + [("Risk", "₹1,400–₹1,500 intended actual risk • maximum 2 positions"), ("Entry window", "09:45–14:00 IST"), ("Monitoring", "LIVE LTP • no candle-close confirmation"), ("Square-off", "15:00 IST")], columns=["Rule", "Definition"]), width="stretch", hide_index=True)

# ---------------- DOWNLOADS ----------------
with st.expander("⬇️ Downloads — all S1 data", expanded=False):
    def csv_bytes(frame): return frame.to_csv(index=False).encode("utf-8")
    def json_bytes(name, fallback):
        path = ROOT / "outputs" / name
        try: return path.read_bytes() if path.exists() else json.dumps(fallback, indent=2).encode("utf-8")
        except Exception: return json.dumps(fallback, indent=2).encode("utf-8")
    gaps = read(ROOT / "outputs/gap_analysis.csv", "csv")
    st.download_button("⬇️ TRADES CSV", data=csv_bytes(trades), file_name="nifty500_trades.csv", mime="text/csv", width="stretch")
    st.download_button("⬇️ SIGNALS CSV", data=csv_bytes(signals), file_name="nifty500_signals.csv", mime="text/csv", width="stretch")
    st.download_button("⬇️ PREMARKET GAP BOARD CSV", data=csv_bytes(gaps), file_name="nifty500_premarket_gap_board.csv", mime="text/csv", width="stretch")
    st.download_button("⬇️ WAITING / QUALIFIED JSON", data=json_bytes("waiting_candidates.json", {"waiting":{},"qualified":{}}), file_name="nifty500_waiting_candidates.json", mime="application/json", width="stretch")
    st.download_button("⬇️ SCANNER DIAGNOSTICS JSON", data=json_bytes("scanner_diagnostics.json", {}), file_name="nifty500_scanner_diagnostics.json", mime="application/json", width="stretch")
    st.download_button("⬇️ BOT STATUS JSON", data=json_bytes("bot_status.json", {}), file_name="nifty500_bot_status.json", mime="application/json", width="stretch")
    st.download_button("⬇️ PAPER STATE JSON", data=json_bytes("paper_engine_state.json", {"strategy":"STRATEGY_1","open_positions":{}}), file_name="nifty500_paper_state.json", mime="application/json", width="stretch")
    if not gaps.empty:
        with st.expander("📌 GAP Board Preview", expanded=False): st.dataframe(gaps, width="stretch", hide_index=True, height=350)

st.caption(f"Heartbeat: {status.get('heartbeat','—')} • Last scan: {diag.get('timestamp','—')} • Strategy 1 single-page mode • UI refresh: 5s")
render_daily_footer()
