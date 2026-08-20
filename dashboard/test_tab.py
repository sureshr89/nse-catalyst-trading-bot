"""Dashboard-only TEST panel.

The TEST position is an in-memory diagnostic only. It never writes signals,
trades, journal, P&L/W-L files, and never touches S1-S5.
"""
import datetime as dt

import pandas as pd
import streamlit as st


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
# Test entry: first qualifying live cycle at or after 09:15 IST.
# There is deliberately no 09:45 deadline: if a complete aligned snapshot
# becomes available at any time after market open, the test may enter then.
TEST_ENTRY_TIME = dt.time(9, 15)
FORCE_EXIT = dt.time(14, 45)
MIN_HOLD = dt.timedelta(minutes=1)
SL_PCT = 0.005
TARGET_PCT = 0.010


def _fmt(v, digits=2):
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "—"


def _now_ist():
    return dt.datetime.now(IST)


def _test_state():
    return st.session_state.setdefault("nse_test_trade", {"date": None, "status": "WAITING"})


def _eligible_stock(rows, index_change):
    if rows is None or rows.empty:
        return None
    work = rows.copy()
    for c in ["LTP", "TodayOpen", "PreviousClose", "NetChange"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")
    work = work.dropna(subset=["Symbol", "LTP", "TodayOpen"])
    if work.empty:
        return None

    # Simple isolated diagnostic rule: positive NIFTY -> first verified stock
    # above open is BUY; negative NIFTY -> first verified stock below open is SELL.
    if float(index_change) >= 0:
        candidates = work[work["LTP"] > work["TodayOpen"]].sort_values("Symbol")
        side = "BUY"
    else:
        candidates = work[work["LTP"] < work["TodayOpen"]].sort_values("Symbol")
        side = "SELL"
    if candidates.empty:
        return None
    r = candidates.iloc[0]
    return {"symbol": str(r["Symbol"]), "side": side, "entry": float(r["LTP"]), "open": float(r["TodayOpen"])}


def _open_test_trade(candidate, now):
    entry = candidate["entry"]
    side = candidate["side"]
    if side == "BUY":
        sl = entry * (1 - SL_PCT)
        target = entry * (1 + TARGET_PCT)
    else:
        sl = entry * (1 + SL_PCT)
        target = entry * (1 - TARGET_PCT)
    st.session_state["nse_test_trade"] = {
        "date": now.date().isoformat(),
        "status": "OPEN",
        "symbol": candidate["symbol"],
        "side": side,
        "entry_time": now.isoformat(),
        "entry": entry,
        "open": candidate["open"],
        "sl": sl,
        "target": target,
        "qty": 1,
        "exit_time": None,
        "exit": None,
        "pnl": None,
        "exit_reason": None,
    }


def _update_test_trade(live_rows, now):
    state = _test_state()
    if state.get("status") != "OPEN":
        return state
    row = live_rows[live_rows["Symbol"].astype(str) == str(state.get("symbol"))]
    if row.empty:
        return state
    ltp = float(row.iloc[0]["LTP"])
    state["last_ltp"] = ltp
    try:
        entry_time = dt.datetime.fromisoformat(state["entry_time"])
    except Exception:
        return state
    if now - entry_time < MIN_HOLD:
        return state

    side = state["side"]
    reason = None
    if side == "BUY":
        if ltp <= state["sl"]:
            reason = "SL"
        elif ltp >= state["target"]:
            reason = "TARGET"
    else:
        if ltp >= state["sl"]:
            reason = "SL"
        elif ltp <= state["target"]:
            reason = "TARGET"
    if reason is None and now.time() >= FORCE_EXIT:
        reason = "2:45 PM TIME EXIT"
    if reason is not None:
        state["status"] = "CLOSED"
        state["exit_time"] = now.isoformat()
        state["exit"] = ltp
        state["exit_reason"] = reason
        state["pnl"] = (ltp - state["entry"]) * state["qty"] if side == "BUY" else (state["entry"] - ltp) * state["qty"]
    return state


def _render_test_trade(rows, snap, idx):
    st.markdown("### 5. 🧪 One isolated test trade — first available time after 09:15 AM to 02:45 PM")
    st.caption(
        "After 09:15 IST, the first refresh with complete aligned live data and a qualifying stock opens the one test position. "
        "There is no 09:45 deadline. Minimum 1-minute hold. SL/Target may close after 1 minute; otherwise forced exit at 02:45 PM IST. "
        "In-memory only; nothing is written to trading or journal storage."
    )
    now = _now_ist()
    state = _test_state()
    today = now.date().isoformat()

    if state.get("date") != today:
        state = {"date": today, "status": "WAITING"}
        st.session_state["nse_test_trade"] = state

    complete = bool(snap.get("complete")) and len(rows) == 500
    sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
    idx_change = float(idx.get("NetChange") or 0) if idx else 0.0
    aligned = complete and sector_ok and bool(idx) and snap.get("ad_ratio") is not None

    if state.get("status") == "WAITING":
        if now.time() >= TEST_ENTRY_TIME:
            if aligned:
                candidate = _eligible_stock(rows, idx_change)
                if candidate:
                    _open_test_trade(candidate, now)
                    state = st.session_state["nse_test_trade"]
                else:
                    st.info("Aligned live data is available, but no stock currently matches the simple price-vs-open side. The test will check again on the next 15-second refresh.")
            else:
                st.info("Waiting for the complete aligned 500-stock/sector/index/A-D snapshot. The test will check again on the next 15-second refresh.")
        else:
            st.info("Waiting for market-open test window: first available qualifying cycle at/after 09:15 AM IST.")

    if state.get("status") == "OPEN":
        state = _update_test_trade(rows, now)

    if state.get("status") in {"OPEN", "CLOSED"}:
        symbol = state.get("symbol", "—")
        current = state.get("last_ltp", state.get("entry"))
        pnl = state.get("pnl")
        cols = st.columns(4)
        cols[0].metric("Stock / Side", f"{symbol} / {state.get('side', '—')}")
        cols[1].metric("Entry", f"₹{_fmt(state.get('entry'))}")
        cols[2].metric("Current / Exit", f"₹{_fmt(current if state.get('status') == 'OPEN' else state.get('exit'))}")
        cols[3].metric("P&L", f"₹{_fmt(pnl) if pnl is not None else '—'}")

        cols = st.columns(4)
        cols[0].metric("Entry Time", state.get("entry_time", "—")[-14:-6] if state.get("entry_time") else "—")
        cols[1].metric("SL", f"₹{_fmt(state.get('sl'))}")
        cols[2].metric("Target", f"₹{_fmt(state.get('target'))}")
        cols[3].metric("Status", state.get("status", "—"))
        if state.get("status") == "CLOSED":
            st.success(f"Test exit: {state.get('exit_reason', '—')} at ₹{_fmt(state.get('exit'))}. Temporary result only; not added to P&L/W-L or journal storage.")
        else:
            st.info("Test position is live in-memory only. It will close on SL/Target after the 1-minute minimum hold, or automatically at 02:45 PM IST.")


def render_test_tab():
    st.markdown("## 🧪 TEST — Live Data / Entry Check")
    st.caption("READ-ONLY diagnostic • one isolated in-memory test position • no signals • no journal • S1–S5 unchanged")

    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured, index_quote

        snap = BREADTH.snapshot(force=False)
        q = snap.get("quote_rows")
        rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
        complete = bool(snap.get("complete")) and len(rows) == 500
        sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
        idx = index_quote("NIFTY 500")

        st.markdown("### 1. Data integrity")
        checks = [("Dhan", configured()), ("Stocks", complete), ("Sectors", sector_ok), ("NIFTY 500", bool(idx)), ("A/D", snap.get("ad_ratio") is not None)]
        cols = st.columns(5)
        for col, (label, ok) in zip(cols, checks):
            with col:
                st.markdown(f'<div class="test-card"><div class="test-label">{label}</div><div class="test-status {"pass" if ok else "wait"}">{"PASS" if ok else "WAIT"}</div></div>', unsafe_allow_html=True)

        st.markdown("### 2. NIFTY 500 live index")
        if idx:
            ltp = float(idx.get("LTP") or 0); prev = float(idx.get("PreviousClose") or 0); net = float(idx.get("NetChange") or (ltp - prev)); pct = (net / prev * 100) if prev else 0.0
            a, b, c, d = st.columns(4)
            a.metric("LTP", f"₹{ltp:,.2f}"); b.metric("Previous Close", f"₹{prev:,.2f}"); c.metric("Change", f"{net:+,.2f}"); d.metric("Change %", f"{pct:+.2f}%")
        else:
            st.warning("NIFTY 500 quote not available in this cycle.")

        st.markdown("### 3. Breadth & sectors")
        a, b, c, d, e = st.columns(5)
        a.metric("Advances", int(snap.get("advances", 0) or 0)); b.metric("Declines", int(snap.get("declines", 0) or 0)); c.metric("Unchanged", int(snap.get("unchanged", 0) or 0)); d.metric("A / D", _fmt(snap.get("ad_ratio"), 2) if snap.get("ad_ratio") is not None else "—"); e.metric("Sectors + / −", f"{int(snap.get('positive_sectors', 0) or 0)} / {int(snap.get('negative_sectors', 0) or 0)}")

        st.markdown("### 4. Five-stock live sample")
        if not rows.empty:
            work = rows.copy()
            for col in ["LTP", "TodayOpen", "PreviousClose", "NetChange"]:
                if col in work.columns: work[col] = pd.to_numeric(work[col], errors="coerce")
            work["ChangePct"] = (work["NetChange"] / work["PreviousClose"] * 100).round(2) if "NetChange" in work.columns else ((work["LTP"] - work["PreviousClose"]) / work["PreviousClose"] * 100).round(2)
            work["SideCheck"] = work.apply(lambda r: "BUY" if r["LTP"] > r["TodayOpen"] else "SELL" if r["LTP"] < r["TodayOpen"] else "FLAT", axis=1)
            display = work.head(5).rename(columns={"Symbol":"Stock","LTP":"LTP ₹","TodayOpen":"Open ₹","ChangePct":"Change %","SideCheck":"Price vs Open"})
            keep = [c for c in ["Stock","LTP ₹","Open ₹","Change %","Price vs Open"] if c in display.columns]
            st.dataframe(display[keep], use_container_width=True, hide_index=True)
        else:
            st.warning("Waiting for the verified 500-stock snapshot.")

        _render_test_trade(rows, snap, idx)
        st.markdown("### TEST isolation")
        st.info("The test position is memory-only for this browser session. It does not write signals.csv, trades.csv, journal data, win/loss, P&L, or S1–S5 state.")

        st.markdown("""<style>
        .test-card{background:#0b1726;border:1px solid #294b70;border-radius:10px;padding:10px 12px;min-height:72px;margin-bottom:8px}.test-label{font-size:12px;color:#9fb0c3;margin-bottom:7px;font-weight:600}.test-status{display:inline-block;font-size:14px;font-weight:700;padding:3px 10px;border-radius:14px}.test-status.pass{background:#063d22;color:#57e389}.test-status.wait{background:#3a2b05;color:#ffd45a}[data-testid="stDataFrame"]{font-size:13px}
        </style>""", unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
