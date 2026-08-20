"""Dashboard-only TEST trade panel. In-memory only; never touches S1-S5 or journals."""
import datetime as dt
import pandas as pd
import streamlit as st

IST=dt.timezone(dt.timedelta(hours=5,minutes=30)); ENTRY_START=dt.time(9,15); FORCE_EXIT=dt.time(14,45)

def _fmt(v,digits=2):
    try:return f"{float(v):,.{digits}f}"
    except Exception:return "—"

def _now_ist():return dt.datetime.now(IST)
def _test_state():return st.session_state.setdefault("nse_test_trade",{"date":None,"status":"WAITING"})

def _alignment(snap,idx):
    if not idx or snap.get("ad_ratio") is None:return None
    try:
        net=float(idx.get("NetChange") or 0); ad=float(snap.get("ad_ratio") or 0); pos=int(snap.get("positive_sectors",0) or 0); neg=int(snap.get("negative_sectors",0) or 0)
        if net>0 and ad>1 and pos>neg:return "BUY"
        if net<0 and ad<1 and neg>pos:return "SELL"
    except Exception:pass
    return None

def _eligible_stock(rows,side):
    if rows is None or rows.empty:return None
    work=rows.copy()
    for c in ["LTP","TodayOpen"]:
        if c in work.columns:work[c]=pd.to_numeric(work[c],errors="coerce")
    work=work.dropna(subset=["Symbol","LTP","TodayOpen"]); work=work[work["LTP"]>work["TodayOpen"]] if side=="BUY" else work[work["LTP"]<work["TodayOpen"]]
    if work.empty:return None
    r=work.sort_values("Symbol").iloc[0];return {"symbol":str(r["Symbol"]),"entry":float(r["LTP"]),"open":float(r["TodayOpen"])}

def _open_test_trade(candidate,side,now):
    st.session_state["nse_test_trade"]={"date":now.date().isoformat(),"status":"OPEN","symbol":candidate["symbol"],"side":side,"entry_time":now.isoformat(),"entry":candidate["entry"],"open":candidate["open"],"exit_time":None,"exit":None,"pnl":None,"exit_reason":None}

def _update_test_trade(rows,now):
    state=_test_state()
    if state.get("status")!="OPEN":return state
    row=rows[rows["Symbol"].astype(str)==str(state.get("symbol"))]
    if row.empty:return state
    ltp=float(row.iloc[0]["LTP"]);state["last_ltp"]=ltp;state["last_update_time"]=now.isoformat()
    side=state.get("side","BUY")
    state["pnl_live"]=ltp-state["entry"] if side=="BUY" else state["entry"]-ltp
    if now.time()>=FORCE_EXIT:
        state.update({"status":"CLOSED","exit_time":now.isoformat(),"exit":ltp,"exit_reason":"2:45 PM TIME EXIT","pnl":state["pnl_live"]})
    return state

def _card(label,value,wide=False):
    cls="test-card wide" if wide else "test-card"
    return f'<div class="{cls}"><div class="test-label">{label}</div><div class="test-value">{value}</div></div>'

def _render_test_trade(rows,snap,idx):
    st.markdown("#### 🧪 Test trade")
    st.caption("One isolated paper test trade • first aligned BUY or SELL after 09:15 IST • no SL/Target • live monitoring until 2:45 PM IST")
    now=_now_ist();state=_test_state();today=now.date().isoformat()
    if state.get("date")!=today:state={"date":today,"status":"WAITING"};st.session_state["nse_test_trade"]=state
    complete=bool(snap.get("complete")) and len(rows)==500;sector_ok=bool(snap.get("sector_complete")) and int(snap.get("sector_priced",0) or 0)==500;alignment=_alignment(snap,idx) if complete and sector_ok else None
    if state.get("status")=="WAITING":
        if ENTRY_START<=now.time()<FORCE_EXIT:
            if alignment:
                candidate=_eligible_stock(rows,alignment)
                if candidate:_open_test_trade(candidate,alignment,now);state=st.session_state["nse_test_trade"]
                else:st.info(f"{alignment} alignment is present, but no matching NIFTY 500 stock is available. Checking again in 15 seconds.")
            else:st.info("Waiting for aligned BUY or SELL: NIFTY direction + A/D + sector breadth + complete 500/500 data.")
        elif now.time()<ENTRY_START:st.info("Waiting for market open. The first aligned BUY or SELL after 09:15 AM will be used.")
        else:st.info("Today's test-entry window has ended. No late test entry will be created.")
    if state.get("status")=="OPEN":state=_update_test_trade(rows,now)
    if state.get("status") in {"OPEN","CLOSED"}:
        side=state.get("side","BUY");price=state.get("exit") if state.get("status")=="CLOSED" else state.get("last_ltp",state.get("entry"));pnl=state.get("pnl") if state.get("status")=="CLOSED" else state.get("pnl_live",0);last_update=state.get("last_update_time")
        status="OPEN • LIVE" if state.get("status")=="OPEN" else "CLOSED"
        st.markdown("<div class='test-grid'>"+_card("STATUS",status)+_card("STOCK / SIDE",f"{state.get('symbol','—')} / {side}")+_card("ENTRY",f"₹{_fmt(state.get('entry'))}")+_card("LIVE / EXIT",f"₹{_fmt(price)}")+_card("LIVE P&L",f"₹{_fmt(pnl)}")+_card("ENTRY TIME",state.get("entry_time","—")[11:19] if state.get("entry_time") else "—")+_card("LAST UPDATE",last_update[11:19] if last_update else "—")+_card("EXIT TIME",state.get("exit_time","—")[11:19] if state.get("exit_time") else "—")+"</div>",unsafe_allow_html=True)
        if state.get("status")=="CLOSED":st.success(f"Exited at 2:45 PM IST • ₹{_fmt(state.get('exit'))} • P&L ₹{_fmt(state.get('pnl'))}")
        else:st.info(f"LIVE: {side} • price and P&L update every 15 seconds • no SL/Target • automatic exit at 2:45 PM IST")

def render_test_tab():
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import index_quote
        snap=BREADTH.snapshot(force=False);q=snap.get("quote_rows");rows=q.copy() if isinstance(q,pd.DataFrame) else pd.DataFrame();idx=index_quote("NIFTY 500");_render_test_trade(rows,snap,idx)
        st.markdown("""<style>
        .test-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:5px 0 12px}
        .test-card{background:#101b2b;border:1px solid #294367;border-radius:9px;padding:8px 10px;min-height:54px;box-sizing:border-box}
        .test-label{font-size:.54rem;color:#fff;line-height:1.15;margin-bottom:5px;font-weight:850;text-transform:uppercase}
        .test-value{font-size:.88rem;color:#fff;line-height:1.15;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        @media(max-width:1000px){.test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.test-value{font-size:.82rem}}
        </style>""",unsafe_allow_html=True)
    except Exception as exc:st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
