"""NSE Catalyst dashboard: presentation only; strategy engine remains untouched."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

def read_csv(name):
    p = OUTPUTS / name
    try: return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception: return pd.DataFrame()

def num(v, default=""):
    try:
        x=float(v); return x if pd.notna(x) else default
    except Exception: return default

def fmt(v):
    if v is None or v=="" or (isinstance(v,float) and pd.isna(v)): return "—"
    try: return f"{float(v):,.2f}"
    except Exception: return str(v)

def first(row,*names,default=""):
    if row is None: return default
    for name in names:
        if name in row.index:
            value=row.get(name)
            if value is not None and str(value).strip() not in {"","nan","NaT"}: return value
    return default

def card(label,value):
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'

st.markdown("""
<style>
.stApp{background:#000!important;color:#f5f7fb}.block-container{max-width:1450px;padding:.7rem .8rem 2rem}
.title{font-size:clamp(1.5rem,4vw,2.4rem);font-weight:900;color:#f5f7fb}.sub{font-size:.75rem;color:#9fb1ca;margin-bottom:10px}
.sec{font-size:1.1rem;font-weight:900;margin:15px 0 8px;color:#fff}.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}
.card,.status{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:10px}.card{min-height:60px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}.value{font-size:.95rem;font-weight:850;margin-top:4px}.status{margin:7px 0;color:#d9e3f1;font-size:.76rem}
.strategy{background:#0b1422;border:1px solid #294367;border-radius:12px;padding:10px;margin:7px 0}.strategy-title{font-weight:900;font-size:.88rem;margin-bottom:7px}.state{float:right;font-weight:900;font-size:.68rem;padding:4px 7px;border-radius:7px;background:#162943}
.trade-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}.trade-cell{background:#101b2b;border-radius:7px;padding:6px}.trade-label{font-size:.5rem;color:#8499b4;text-transform:uppercase}.trade-value{font-size:.7rem;font-weight:800;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tip{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:13px;font-weight:700}
@media(max-width:900px){.grid6{grid-template-columns:repeat(3,1fr)}.trade-grid{grid-template-columns:repeat(4,1fr)}}@media(max-width:600px){.grid6{grid-template-columns:repeat(2,1fr)}.trade-grid{grid-template-columns:repeat(2,1fr)}}
</style>
""",unsafe_allow_html=True)

@st.fragment(run_every="15s")
def live_dashboard():
    now=datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured,dhan_status
        market=BREADTH.snapshot(force=False); dhan_ok=dhan_configured(); api_status=dhan_status()
    except Exception as exc:
        market={"complete":False,"sector_complete":False,"evaluated":0,"sector_priced":0,"nifty500_change_pct":None,"sector_alignment_pct":None,"ad_ratio":None}
        dhan_ok=False; api_status={"ok":False,"received":0,"requested":0,"message":str(exc)}

    trades_all=read_csv("trades.csv"); signals_all=read_csv("signals.csv"); today=now.date()
    trades_today=trades_all.copy()
    if not trades_today.empty:
        dc=next((c for c in ["exit_time","entry_time","market_entry_time","trigger_entry_time"] if c in trades_today.columns),None)
        if dc:
            d=pd.to_datetime(trades_today[dc],errors="coerce",utc=True)
            try: d=d.dt.tz_convert(IST)
            except Exception: pass
            trades_today=trades_today[d.dt.date==today]
    signals_today=signals_all.copy()
    if not signals_today.empty:
        dc=next((c for c in ["timestamp","entry_time","logged_at"] if c in signals_today.columns),None)
        if dc:
            d=pd.to_datetime(signals_today[dc],errors="coerce",utc=True)
            try: d=d.dt.tz_convert(IST)
            except Exception: pass
            signals_today=signals_today[d.dt.date==today]
    master_csv=trades_all.copy()

    n=market.get("nifty500_change_pct"); sec=market.get("sector_alignment_pct"); ad=market.get("ad_ratio"); evaln=int(market.get("evaluated",0) or 0); sp=int(market.get("sector_priced",0) or 0)
    buy=bool(market.get("complete") and market.get("sector_complete") and num(n,0)>0 and num(sec,0)>0 and num(ad,0)>1)
    sell=bool(market.get("complete") and market.get("sector_complete") and num(n,0)<0 and num(sec,0)<0 and num(ad,2)<1)
    bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
    st.markdown('<div class="title">📊 NSE Catalyst — Master Dashboard</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan • {now.strftime("%d %b %Y %H:%M:%S")} IST • auto refresh 15s</div>',unsafe_allow_html=True)
    st.markdown('<div class="sec">🎯 Master Market Alignment</div>',unsafe_allow_html=True)
    cards=[("NIFTY 500",f"{num(n,'—')}%" if n not in {None,""} else "—"),("SECTORS",f"{num(sec,'—')}%" if sec not in {None,""} else "—"),("A/D RATIO",fmt(ad) if ad is not None else "WAITING"),("BREADTH",f"{evaln}/500"),("SECTOR DATA",f"{sp}/500"),("MASTER BIAS",bias)]
    st.markdown('<div class="grid6">'+''.join(card(l,v) for l,v in cards)+'</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="status"><b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if api_status.get("ok") else "WAIT/ERROR"} • Quotes {api_status.get("received",0)}/{api_status.get("requested",0)} • Every value refreshes with this 15s cycle</div>',unsafe_allow_html=True)

    st.markdown('<div class="sec">⚡ S1–S5 — TODAY\'S ACTUAL TRADE STATE</div>',unsafe_allow_html=True)
    for strategy in ["S1","S2","S3","S4","S5"]:
        tr=pd.DataFrame(); sg=pd.DataFrame()
        for source,target in [(trades_today,"tr"),(signals_today,"sg")]:
            if source.empty: continue
            cols=[c for c in ["strategy","strategy_name","signal","setup_type"] if c in source.columns]
            if not cols: continue
            mask=pd.Series(False,index=source.index)
            for c in cols:
                vals=source[c].astype(str).str.upper().str.strip(); mask|=vals.eq(strategy)|vals.str.startswith(strategy+" ")
            if target=="tr": tr=source[mask]
            else: sg=source[mask]
        row=tr.iloc[-1] if not tr.empty else None; signal_row=sg.iloc[-1] if not sg.empty else None
        if row is not None:
            status=str(first(row,"status",default="OPEN")).upper(); state="CLOSED" if status=="CLOSED" or first(row,"exit_time") not in {"",None} else "TRADE OPEN"
            stock=first(row,"symbol","stock"); side=first(row,"buy_sell","side","signal"); signal_time=first(row,"trigger_entry_time","entry_time","market_entry_time"); entry=first(row,"entry","entry_price"); sl=first(row,"stop_loss"); target=first(row,"target"); exit_price=first(row,"exit_price","exit"); pnl=first(row,"pnl"); rr=first(row,"rr","reward","risk_reward"); qty=first(row,"quantity"); exit_reason=first(row,"exit_reason")
        elif signal_row is not None:
            state="SIGNAL"; stock=first(signal_row,"symbol","stock"); side=first(signal_row,"buy_sell","side","signal"); signal_time=first(signal_row,"timestamp","entry_time","logged_at"); entry=first(signal_row,"entry","entry_price"); sl=first(signal_row,"stop_loss"); target=first(signal_row,"target"); exit_price=pnl=""; rr=first(signal_row,"risk_reward","rr","reward"); qty=first(signal_row,"quantity"); exit_reason=""
        else:
            state="WAITING"; stock=side=signal_time=entry=sl=target=exit_price=pnl=rr=qty=exit_reason=""
        color="#67e8a5" if state=="CLOSED" else "#5ec8ff" if state=="SIGNAL" else "#ffd166" if state=="TRADE OPEN" else "#9fb1ca"
        cells=[("Stock",stock),("BUY / SELL",side),("Signal Time",signal_time),("Entry",fmt(entry)),("Stop Loss",fmt(sl)),("Target",fmt(target)),("Exit",fmt(exit_price)),("P&L",fmt(pnl)),("Risk / Reward",fmt(rr)),("Quantity",fmt(qty)),("Exit Reason",exit_reason or "—")]
        html=''.join(f'<div class="trade-cell"><div class="trade-label">{l}</div><div class="trade-value">{v or "—"}</div></div>' for l,v in cells)
        st.markdown(f'<div class="strategy"><span class="state" style="color:{color}">{state}</span><div class="strategy-title">{strategy}</div><div class="trade-grid">{html}</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="sec">📥 MASTER DOWNLOAD — CUMULATIVE</div>',unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV",master_csv.to_csv(index=False).encode("utf-8"),"nse_catalyst_master.csv","text/csv",use_container_width=True,key="master_csv")
    st.caption(f"Cumulative journal: {len(master_csv)} trade record(s). Original journal columns preserved.")
    st.markdown('<div class="sec">🧠 TODAY\'S JOURNAL</div>',unsafe_allow_html=True)
    pnl_series=pd.to_numeric(trades_today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0); win_rate=f"{(pnl_series>0).mean()*100:.1f}%" if len(pnl_series) else "—"
    cards2=[("TRADES",len(trades_today)),("WINS",int((pnl_series>0).sum())),("LOSSES",int((pnl_series<0).sum())),("WIN RATE",win_rate),("TODAY P&L",f"₹{pnl_series.sum():,.0f}")]
    st.markdown('<div class="grid6">'+''.join(card(l,v) for l,v in cards2)+'</div>',unsafe_allow_html=True)
    if not trades_today.empty: st.dataframe(trades_today,width="stretch",hide_index=True)
    else: st.info("No completed/open trade journal records today.")
    st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>',unsafe_allow_html=True)
    tips=["Follow the setup, not the emotion.","Protect capital first; profits come second.","Wait for confirmation before entering.","One disciplined trade is better than many emotional trades.","Never chase a missed entry."]
    st.markdown(f'<div class="tip">💡 {tips[now.date().toordinal()%len(tips)]}</div>',unsafe_allow_html=True)
    st.caption("NSE Catalyst • paper trading only • dashboard refreshes every 15 seconds")

live_dashboard()
