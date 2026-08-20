"""Dashboard-only TEST trade panel. In-memory only; never touches S1-S5 or journals."""
import datetime as dt
import pandas as pd
import streamlit as st

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
ENTRY_START = dt.time(9, 15)
FORCE_EXIT = dt.time(14, 45)


def _fmt(v, digits=2):
    try: return f"{float(v):,.{digits}f}"
    except Exception: return "—"


def _now_ist(): return dt.datetime.now(IST)


def _test_state():
    return st.session_state.setdefault("nse_test_trade", {"date": None, "status": "WAITING"})


def _aligned_buy(snap, idx):
    if not idx or snap.get("ad_ratio") is None: return False
    try:
        return (float(idx.get("NetChange") or 0) > 0 and
                float(snap.get("ad_ratio") or 0) > 1.0 and
                int(snap.get("positive_sectors", 0) or 0) > int(snap.get("negative_sectors", 0) or 0))
    except Exception: return False


def _eligible_stock(rows):
    if rows is None or rows.empty: return None
    work = rows.copy()
    for c in ["LTP", "TodayOpen"]:
        if c in work.columns: work[c] = pd.to_numeric(work[c], errors="coerce")
    work = work.dropna(subset=["Symbol", "LTP", "TodayOpen"])
    work = work[work["LTP"] > work["TodayOpen"]]
    if work.empty: return None
    r = work.sort_values("Symbol").iloc[0]
    return {"symbol": str(r["Symbol"]), "entry": float(r["LTP"]), "open": float(r["TodayOpen"])}


def _open_test_trade(candidate, now):
    st.session_state["nse_test_trade"] = {
        "date": now.date().isoformat(), "status": "OPEN", "symbol": candidate["symbol"], "side": "BUY",
        "entry_time": now.isoformat(), "entry": candidate["entry"], "open": candidate["open"],
        "exit_time": None, "exit": None, "pnl": None, "exit_reason": None,
    }


def _update_test_trade(rows, now):
    state = _test_state()
    if state.get("status") != "OPEN": return state
    row = rows[rows["Symbol"].astype(str) == str(state.get("symbol"))]
    if row.empty: return state
    ltp = float(row.iloc[0]["LTP"]); state["last_ltp"] = ltp
    if now.time() >= FORCE_EXIT:
        state.update({"status":"CLOSED", "exit_time":now.isoformat(), "exit":ltp, "exit_reason":"2:45 PM TIME EXIT", "pnl":ltp-state["entry"]})
    return state


def _card(label, value):
    return f'<div class="test-card"><div class="test-label">{label}</div><div class="test-value">{value}</div></div>'


def _render_test_trade(rows, snap, idx):
    st.markdown("#### 🧪 One aligned BUY test trade")
    st.caption("First available live cycle after 09:15 IST when NIFTY is positive, A/D > 1, positive sectors exceed negative sectors, 500/500 data is complete, and a stock is above open. One trade only • no SL • no Target • live monitoring until 2:45 PM IST • memory-only.")
    now = _now_ist(); state = _test_state(); today = now.date().isoformat()
    if state.get("date") != today:
        state = {"date": today, "status": "WAITING"}; st.session_state["nse_test_trade"] = state
    complete = bool(snap.get("complete")) and len(rows) == 500
    sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
    aligned = complete and sector_ok and _aligned_buy(snap, idx)
    if state.get("status") == "WAITING":
        if ENTRY_START <= now.time() < FORCE_EXIT:
            if aligned:
                candidate = _eligible_stock(rows)
                if candidate:
                    _open_test_trade(candidate, now); state = st.session_state["nse_test_trade"]
                else: st.info("Alignment is present, but no NIFTY 500 stock is currently above open. Checking again in 15 seconds.")
            else:
                st.info("Waiting for BUY alignment: NIFTY positive + A/D > 1 + positive sectors > negative sectors + complete 500/500 data.")
        elif now.time() < ENTRY_START: st.info("Waiting for market open. The first aligned BUY after 09:15 AM will be used.")
        else: st.info("Today's test-entry window has ended. No late test entry will be created.")
    if state.get("status") == "OPEN": state = _update_test_trade(rows, now)
    if state.get("status") in {"OPEN", "CLOSED"}:
        current = state.get("last_ltp", state.get("entry")); price = current if state.get("status") == "OPEN" else state.get("exit"); pnl = state.get("pnl") if state.get("status") == "CLOSED" else price - state.get("entry")
        st.markdown("<div class='test-grid'>" +
                    _card("Stock / Side", f"{state.get('symbol','—')} / BUY") +
                    _card("Entry", f"₹{_fmt(state.get('entry'))}") +
                    _card("Current / Exit", f"₹{_fmt(price)}") +
                    _card("P&L", f"₹{_fmt(pnl)}") +
                    _card("Entry Time", state.get("entry_time", "—")[11:19] if state.get("entry_time") else "—") +
                    _card("Exit Time", state.get("exit_time", "—")[11:19] if state.get("exit_time") else "—") +
                    "</div>", unsafe_allow_html=True)
        if state.get("status") == "CLOSED": st.success(f"Test exit: {state.get('exit_reason','—')} at ₹{_fmt(state.get('exit'))}. Temporary only; not added to journal/P&L/W-L.")
        else: st.info("One aligned BUY test position is open in memory only. No SL or Target. It will run until 2:45 PM IST.")


def render_test_tab():
    """Only the isolated TEST trade appears here. Master data already exists above."""
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import index_quote
        snap = BREADTH.snapshot(force=False)
        q = snap.get("quote_rows")
        rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
        idx = index_quote("NIFTY 500")
        _render_test_trade(rows, snap, idx)
        st.markdown("#### 💡 Trading tip")
        st.info("One disciplined trade is better than many emotional trades. Use the TEST position only to verify live-data alignment and the entry/exit pipeline; it does not represent a validated S1–S5 signal.")
        st.markdown("""
        <style>
        .test-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:4px 0 14px}
        .test-card{background:#0b1726;border:1px solid #294b70;border-radius:9px;padding:9px 11px;min-height:58px;box-sizing:border-box}
        .test-label{font-size:11px;color:#9fb0c3;line-height:1.2;margin-bottom:6px;font-weight:600;text-transform:uppercase}
        .test-value{font-size:18px;color:#f2f6fa;line-height:1.2;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        @media(max-width:700px){.test-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.test-value{font-size:16px}}
        </style>
        """, unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
