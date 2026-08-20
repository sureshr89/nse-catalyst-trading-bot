"""Dashboard-only TEST panel. In-memory only; never touches S1-S5 or journals."""
import datetime as dt
import pandas as pd
import streamlit as st

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
ENTRY_START = dt.time(9, 15)
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


def _aligned_buy(snap, idx):
    if not idx or snap.get("ad_ratio") is None:
        return False
    try:
        nifty = float(idx.get("NetChange") or 0)
        ad = float(snap.get("ad_ratio") or 0)
        pos = int(snap.get("positive_sectors", 0) or 0)
        neg = int(snap.get("negative_sectors", 0) or 0)
        return nifty > 0 and ad > 1.0 and pos > neg
    except Exception:
        return False


def _eligible_stock(rows):
    if rows is None or rows.empty:
        return None
    work = rows.copy()
    for c in ["LTP", "TodayOpen"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")
    work = work.dropna(subset=["Symbol", "LTP", "TodayOpen"])
    work = work[work["LTP"] > work["TodayOpen"]]
    if work.empty:
        return None
    r = work.sort_values("Symbol").iloc[0]
    return {"symbol": str(r["Symbol"]), "entry": float(r["LTP"]), "open": float(r["TodayOpen"])}


def _open_test_trade(candidate, now):
    entry = candidate["entry"]
    st.session_state["nse_test_trade"] = {
        "date": now.date().isoformat(), "status": "OPEN", "symbol": candidate["symbol"], "side": "BUY",
        "entry_time": now.isoformat(), "entry": entry, "open": candidate["open"],
        "sl": entry * (1 - SL_PCT), "target": entry * (1 + TARGET_PCT), "qty": 1,
        "exit_time": None, "exit": None, "pnl": None, "exit_reason": None,
    }


def _update_test_trade(rows, now):
    state = _test_state()
    if state.get("status") != "OPEN":
        return state
    row = rows[rows["Symbol"].astype(str) == str(state.get("symbol"))]
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
    reason = None
    if ltp <= state["sl"]:
        reason = "SL"
    elif ltp >= state["target"]:
        reason = "TARGET"
    elif now.time() >= FORCE_EXIT:
        reason = "2:45 PM TIME EXIT"
    if reason:
        state.update({"status": "CLOSED", "exit_time": now.isoformat(), "exit": ltp,
                      "exit_reason": reason, "pnl": (ltp - state["entry"]) * state["qty"]})
    return state


def _card(label, value, status=None):
    status_html = ""
    if status is not None:
        cls = "pass" if status else "wait"
        status_html = f'<span class="test-status {cls}">{"PASS" if status else "WAIT"}</span>'
    return f'<div class="test-card"><div class="test-label">{label}</div><div class="test-value">{value}</div>{status_html}</div>'


def _render_test_trade(rows, snap, idx):
    st.markdown("#### 🧪 One isolated aligned BUY test trade")
    st.caption("First available 15-second cycle at/after 09:15 IST: NIFTY positive + A/D > 1 + positive sectors > negative sectors + stock above open. Exactly one test trade. Minimum 1-minute hold. SL 0.5% / Target 1%. Otherwise exit 2:45 PM IST. Memory-only.")
    now = _now_ist()
    state = _test_state()
    today = now.date().isoformat()
    if state.get("date") != today:
        state = {"date": today, "status": "WAITING"}
        st.session_state["nse_test_trade"] = state

    complete = bool(snap.get("complete")) and len(rows) == 500
    sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
    aligned = complete and sector_ok and _aligned_buy(snap, idx)

    if state.get("status") == "WAITING":
        if ENTRY_START <= now.time() < FORCE_EXIT:
            if aligned:
                candidate = _eligible_stock(rows)
                if candidate:
                    _open_test_trade(candidate, now)
                    state = st.session_state["nse_test_trade"]
                else:
                    st.info("Alignment is present, but no NIFTY 500 stock is currently above open. Checking again in 15 seconds.")
            else:
                st.info("Waiting for BUY alignment: NIFTY positive + A/D > 1 + positive sectors > negative sectors + complete 500/500 data.")
        elif now.time() < ENTRY_START:
            st.info("Waiting for market open. First aligned BUY after 09:15 AM will be used.")
        else:
            st.info("Today's test-entry window has ended. No late test entry will be created.")

    if state.get("status") == "OPEN":
        state = _update_test_trade(rows, now)

    if state.get("status") in {"OPEN", "CLOSED"}:
        current = state.get("last_ltp", state.get("entry"))
        price = current if state.get("status") == "OPEN" else state.get("exit")
        pnl = state.get("pnl")
        st.markdown("<div class='test-grid'>" +
                    _card("Stock / Side", f"{state.get('symbol', '—')} / BUY") +
                    _card("Entry", f"₹{_fmt(state.get('entry'))}") +
                    _card("Current / Exit", f"₹{_fmt(price)}") +
                    _card("P&L", f"₹{_fmt(pnl) if pnl is not None else '—'}") +
                    _card("Entry Time", state.get("entry_time", "—")[11:19] if state.get("entry_time") else "—") +
                    _card("SL", f"₹{_fmt(state.get('sl'))}") +
                    _card("Target", f"₹{_fmt(state.get('target'))}") +
                    _card("Exit Time", state.get("exit_time", "—")[11:19] if state.get("exit_time") else "—") +
                    "</div>", unsafe_allow_html=True)
        if state.get("status") == "CLOSED":
            st.success(f"Test exit: {state.get('exit_reason', '—')} at ₹{_fmt(state.get('exit'))}. Temporary only; not added to journal/P&L/W-L.")
        else:
            st.info("One aligned BUY test position is open in memory only. No second test trade will be taken today.")


def render_test_tab():
    st.markdown("### 🧪 TEST — Live Data / Entry Check")
    st.caption("READ-ONLY diagnostic • one isolated in-memory BUY test • no signals • no journal • S1–S5 unchanged")
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured, index_quote
        snap = BREADTH.snapshot(force=False)
        q = snap.get("quote_rows")
        rows = q.copy() if isinstance(q, pd.DataFrame) else pd.DataFrame()
        complete = bool(snap.get("complete")) and len(rows) == 500
        sector_ok = bool(snap.get("sector_complete")) and int(snap.get("sector_priced", 0) or 0) == 500
        idx = index_quote("NIFTY 500")

        st.markdown("#### 1. Data integrity")
        checks = [("Dhan", configured()), ("Stocks 500/500", complete), ("Sectors 500/500", sector_ok), ("NIFTY 500", bool(idx)), ("A / D", snap.get("ad_ratio") is not None)]
        st.markdown("<div class='test-grid test-grid-5'>" + "".join(_card(label, "", ok) for label, ok in checks) + "</div>", unsafe_allow_html=True)

        st.markdown("#### 2. NIFTY 500 live index")
        if idx:
            ltp = float(idx.get("LTP") or 0)
            prev = float(idx.get("PreviousClose") or 0)
            net = float(idx.get("NetChange") or (ltp - prev))
            pct = (net / prev * 100) if prev else 0
            st.markdown("<div class='test-grid'>" + _card("LTP", f"₹{ltp:,.2f}") + _card("Previous Close", f"₹{prev:,.2f}") + _card("Change", f"{net:+,.2f}") + _card("Change %", f"{pct:+.2f}%") + "</div>", unsafe_allow_html=True)
        else:
            st.warning("NIFTY 500 quote not available in this cycle.")

        st.markdown("#### 3. Breadth & sectors")
        st.markdown("<div class='test-grid test-grid-5'>" +
                    _card("Advances", int(snap.get("advances", 0) or 0)) +
                    _card("Declines", int(snap.get("declines", 0) or 0)) +
                    _card("Unchanged", int(snap.get("unchanged", 0) or 0)) +
                    _card("A / D", _fmt(snap.get("ad_ratio"), 2) if snap.get("ad_ratio") is not None else "—") +
                    _card("Sectors + / −", f"{int(snap.get('positive_sectors', 0) or 0)} / {int(snap.get('negative_sectors', 0) or 0)}") +
                    "</div>", unsafe_allow_html=True)

        st.markdown("#### 4. Five-stock live sample")
        if not rows.empty:
            work = rows.copy()
            for col in ["LTP", "TodayOpen", "PreviousClose", "NetChange"]:
                if col in work.columns:
                    work[col] = pd.to_numeric(work[col], errors="coerce")
            work["ChangePct"] = (work["NetChange"] / work["PreviousClose"] * 100).round(2) if "NetChange" in work.columns else ((work["LTP"] - work["PreviousClose"]) / work["PreviousClose"] * 100).round(2)
            work["SideCheck"] = work.apply(lambda r: "BUY" if r["LTP"] > r["TodayOpen"] else "SELL" if r["LTP"] < r["TodayOpen"] else "FLAT", axis=1)
            display = work.head(5).rename(columns={"Symbol": "Stock", "LTP": "LTP ₹", "TodayOpen": "Open ₹", "ChangePct": "Change %", "SideCheck": "Price vs Open"})
            keep = [c for c in ["Stock", "LTP ₹", "Open ₹", "Change %", "Price vs Open"] if c in display.columns]
            st.dataframe(display[keep], use_container_width=True, hide_index=True)
        else:
            st.warning("Waiting for the verified 500-stock snapshot.")

        _render_test_trade(rows, snap, idx)
        st.markdown("#### TEST isolation")
        st.info("The test position is memory-only. It does not write signals.csv, trades.csv, journal data, win/loss, P&L, or S1–S5 state.")
        st.markdown("""
        <style>
        .test-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:4px 0 14px}
        .test-grid-5{grid-template-columns:repeat(5,minmax(0,1fr))}
        .test-card{background:#0b1726;border:1px solid #294b70;border-radius:9px;padding:9px 11px;min-height:58px;box-sizing:border-box}
        .test-label{font-size:11px;color:#9fb0c3;line-height:1.2;margin-bottom:6px;font-weight:600;text-transform:uppercase}
        .test-value{font-size:18px;color:#f2f6fa;line-height:1.2;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .test-status{display:inline-block;font-size:11px;font-weight:700;padding:3px 9px;border-radius:12px;margin-top:5px}
        .test-status.pass{background:#063d22;color:#57e389}.test-status.wait{background:#3a2b05;color:#ffd45a}
        @media(max-width:700px){.test-grid,.test-grid-5{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.test-grid-5 .test-card:last-child{grid-column:1/-1}.test-value{font-size:16px}}
        [data-testid="stDataFrame"]{font-size:13px}
        </style>
        """, unsafe_allow_html=True)
    except Exception as exc:
        st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
