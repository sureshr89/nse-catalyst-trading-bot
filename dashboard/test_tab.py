"""Dashboard-only TEST trade panel: one daily paper trade, live every 15s."""
import datetime as dt
import json
from pathlib import Path
import pandas as pd
import streamlit as st

IST=dt.timezone(dt.timedelta(hours=5,minutes=30)); ENTRY_START=dt.time(9,15); FORCE_EXIT=dt.time(14,45)
STATE_FILE=Path(__file__).resolve().parents[1]/"outputs"/"test_trade_state.json"

def _fmt(v,digits=2):
    try:return f"{float(v):,.{digits}f}"
    except Exception:return "—"
def _now_ist():return dt.datetime.now(IST)
def _load(today):
    try:
        if STATE_FILE.exists():
            s=json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if s.get("date")==today:return s
    except Exception:pass
    return {"date":today,"status":"WAITING"}
def _save(s):
    try:
        STATE_FILE.parent.mkdir(parents=True,exist_ok=True);tmp=STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(STATE_FILE)
    except Exception:pass
def _state(today):
    s=st.session_state.get("nse_test_trade")
    if not s or s.get("date")!=today:s=_load(today);st.session_state["nse_test_trade"]=s
    return s

def _alignment(snap,idx):
    if not idx or snap.get("ad_ratio") is None:return None
    try:
        net=float(idx.get("NetChange") or 0);ad=float(snap.get("ad_ratio") or 0);pos=int(snap.get("positive_sectors",0) or 0);neg=int(snap.get("negative_sectors",0) or 0)
        if net>0 and ad>1 and pos>neg:return "BUY"
        if net<0 and ad<1 and neg>pos:return "SELL"
    except Exception:pass
    return None

def _candidate(rows,side):
    if rows is None or rows.empty:return None
    w=rows.copy()
    for c in ["LTP","TodayOpen"]:
        if c in w.columns:w[c]=pd.to_numeric(w[c],errors="coerce")
    w=w.dropna(subset=["Symbol","LTP","TodayOpen"]);w=w[w["LTP"]>w["TodayOpen"]] if side=="BUY" else w[w["LTP"]<w["TodayOpen"]]
    if w.empty:return None
    r=w.sort_values("Symbol").iloc[0];return {"symbol":str(r["Symbol"]),"entry":float(r["LTP"]),"open":float(r["TodayOpen"])}

def _open(c,side,now):
    s={"date":now.date().isoformat(),"status":"OPEN","symbol":c["symbol"],"side":side,"entry_time":now.isoformat(),"entry":c["entry"],"open":c["open"],"last_ltp":c["entry"],"last_update_time":now.isoformat(),"exit_time":None,"exit":None,"pnl_live":0.0,"pnl":None,"exit_reason":None}
    st.session_state["nse_test_trade"]=s;_save(s);return s

def _update(rows,now,s):
    if s.get("status")!="OPEN":return s
    try:
        sym=str(s.get("symbol"));r=rows[rows["Symbol"].astype(str)==sym] if rows is not None and not rows.empty else pd.DataFrame()
        if not r.empty:
            ltp=float(r.iloc[0]["LTP"]);s["last_ltp"]=ltp;s["last_update_time"]=now.isoformat();s["pnl_live"]=ltp-float(s["entry"]) if s.get("side")=="BUY" else float(s["entry"])-ltp
    except Exception:pass
    if now.time()>=FORCE_EXIT:
        s.update({"status":"CLOSED","exit_time":now.isoformat(),"exit":s.get("last_ltp",s.get("entry")),"exit_reason":"2:45 PM TIME EXIT","pnl":s.get("pnl_live",0.0),"last_update_time":now.isoformat()})
    st.session_state["nse_test_trade"]=s;_save(s);return s

def _card(label,value):return f'<div class="test-card"><div class="test-label">{label}</div><div class="test-value">{value}</div></div>'

@st.fragment(run_every="15s")
def _live_test():
    # IMPORTANT: fetch fresh Dhan/breadth data INSIDE the fragment. Passing rows
    # from the parent function would freeze the quote snapshot between reruns.
    st.markdown("#### 🧪 Test trade")
    st.caption("One isolated paper trade • first aligned entry at/after 09:15 IST • live Dhan P&L every 15 seconds • forced exit 14:45 IST")
    now=_now_ist();today=now.date().isoformat();s=_state(today)
    from market.nifty500_breadth import BREADTH
    from market.dhan_data import index_quote
    snap=BREADTH.snapshot(force=True);q=snap.get("quote_rows");rows=q.copy() if isinstance(q,pd.DataFrame) else pd.DataFrame();idx=index_quote("NIFTY 500")
    if s.get("status")=="WAITING" and ENTRY_START<=now.time()<FORCE_EXIT:
        complete=bool(snap.get("complete")) and len(rows)==500;sector_ok=bool(snap.get("sector_complete")) and int(snap.get("sector_priced",0) or 0)==500;alignment=_alignment(snap,idx) if complete and sector_ok else None
        if alignment:
            c=_candidate(rows,alignment)
            if c:s=_open(c,alignment,now)
            else:st.info(f"{alignment} alignment present; waiting for an eligible NIFTY 500 stock.")
        else:st.info("Waiting for complete 500/500 data and BUY/SELL alignment.")
    elif s.get("status")=="WAITING":st.info("Waiting for 09:15 AM IST." if now.time()<ENTRY_START else "Today's entry window is closed; no late entry will be created.")
    if s.get("status")=="OPEN":s=_update(rows,now,s)
    if s.get("status") in {"OPEN","CLOSED"}:
        closed=s.get("status")=="CLOSED";price=s.get("exit") if closed else s.get("last_ltp",s.get("entry"));pnl=s.get("pnl") if closed else s.get("pnl_live",0);et=s.get("entry_time");ut=s.get("last_update_time");xt=s.get("exit_time")
        html="<div class='test-grid'>"+_card("STATUS","CLOSED" if closed else "OPEN • LIVE")+_card("STOCK / SIDE",f"{s.get('symbol','—')} / {s.get('side','—')}")+_card("ENTRY",f"₹{_fmt(s.get('entry'))}")+_card("LIVE / EXIT",f"₹{_fmt(price)}")+_card("LIVE P&L",f"₹{_fmt(pnl)}")+_card("ENTRY TIME",et[11:19] if et else "—")+_card("LAST UPDATE",ut[11:19] if ut else "—")+_card("EXIT TIME",xt[11:19] if xt else "—")+"</div>";st.markdown(html,unsafe_allow_html=True)
        if closed:st.success(f"Exited at 2:45 PM IST • ₹{_fmt(s.get('exit'))} • P&L ₹{_fmt(s.get('pnl'))}")
        else:st.info(f"LIVE: last Dhan quote update {ut[11:19] if ut else '—'} • next refresh in 15 seconds")

def render_test_tab():
    try:
        _live_test()
        st.markdown("""<style>.test-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:5px 0 12px}.test-card{background:#101b2b;border:1px solid #294367;border-radius:9px;padding:8px 10px;min-height:54px}.test-label{font-size:.54rem;color:#fff;margin-bottom:5px;font-weight:850;text-transform:uppercase}.test-value{font-size:.88rem;color:#fff;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}@media(max-width:1000px){.test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>""",unsafe_allow_html=True)
    except Exception as exc:st.error(f"TEST unavailable: {type(exc).__name__}: {exc}")
