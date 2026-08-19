"""Single-page NSE Catalyst master dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
REFRESH = 15
STRATEGIES = {"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}

st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=REFRESH * 1000, key="master_refresh")

try:
    from market.nifty500_breadth import BREADTH
    from market.dhan_data import configured as dhan_configured
    d = BREADTH.snapshot(force=True)
    dhan_ok = dhan_configured()
except Exception as exc:
    d = {"complete":False,"reason":f"{type(exc).__name__}: {exc}","evaluated":0,"total":500,"market_data_source":"DHAN"}
    dhan_ok = False

now = datetime.now(IST)
n = d.get("nifty500_change_pct"); sec = d.get("sector_alignment_pct"); ad = d.get("ad_ratio")
evaln = int(d.get("evaluated",0) or 0); sm = int(d.get("sector_mapped",0) or 0); sp = int(d.get("sector_priced",0) or 0)
complete = bool(d.get("complete")); scomplete = bool(d.get("sector_complete"))
buy = complete and scomplete and n is not None and sec is not None and ad is not None and n > 0 and sec > 0 and ad > 1
sell = complete and scomplete and n is not None and sec is not None and ad is not None and n < 0 and sec < 0 and ad < 1
bias = "🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

def read_csv(name):
    p = OUTPUTS / name
    try: return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception: return pd.DataFrame()

def money(x):
    try: return f"₹{float(x):,.0f}"
    except Exception: return "₹0"

def pct(x):
    try: return f"{float(x):+.2f}%"
    except Exception: return "—"

def card(label,value):
    return f"<div class='card'><small>{label}</small><b>{value}</b></div>"

def norm_strategy(x):
    s = str(x).upper().strip()
    if s in STRATEGIES: return s
    if s.startswith("STRATEGY_"): return "S" + s.split("_")[-1]
    return s

def drawdown(series):
    if series is None or len(series) == 0: return 0.0
    s = pd.to_numeric(series,errors="coerce").fillna(0.0)
    equity = s.cumsum()
    return float((equity - equity.cummax()).min())

st.markdown("""<style>
html,body,[class*="css"]{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}.block-container{max-width:1450px;padding:.8rem .8rem 2rem}
.title{font-size:clamp(1.65rem,4vw,2.65rem);font-weight:900;color:#f4f7fb;margin-bottom:4px}.sub{color:#9fb1ca;font-size:.8rem;margin-bottom:15px}.sec{font-size:1.2rem;font-weight:900;margin:18px 0 9px;color:#f4f7fb}
.grid6{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.card,.strategy{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:10px;min-height:68px}.card small{display:block;color:#9fb1ca;font-size:.58rem;font-weight:850;text-transform:uppercase}.card b{display:block;color:#f4f7fb;font-size:1rem;margin-top:5px}.strategy{min-height:105px}.strategy h4{margin:0 0 6px;font-size:1rem}.muted{color:#9fb1ca;font-size:.78rem}.status{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:10px;margin-top:8px}.green{color:#43d17a}.yellow{color:#ffd166}
@media(max-width:900px){.grid6{grid-template-columns:repeat(3,minmax(0,1fr))}.grid4{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.grid6,.grid4,.grid2{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.card{min-height:62px;padding:8px}.card b{font-size:.88rem}.sec{font-size:1.08rem}.title{font-size:1.6rem}}
</style>""",unsafe_allow_html=True)

st.markdown("<div class='title'>📊 NSE Catalyst — Master Dashboard</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 • PAPER TRADING ONLY • Dhan data layer • refresh {REFRESH}s • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🎯 Master Market Alignment</div>",unsafe_allow_html=True)
st.markdown("<div class='grid6'>"+"".join([card("NIFTY 500",pct(n)),card("SECTORS",pct(sec)),card("A/D RATIO",f"{float(ad):.2f}" if ad is not None else "WAITING"),card("BREADTH",f"{evaln}/500"),card("SECTOR DATA",f"{sp}/500"),card("MASTER BIAS",bias)])+"</div>",unsafe_allow_html=True)
if complete and scomplete:
    st.markdown(f"<div class='status'><span class='green'><b>● DHAN LIVE DATA READY</b></span> • 500/500 stocks • Advances {d.get('advances','—')} • Declines {d.get('declines','—')} • A/D {float(ad):.2f}</div>",unsafe_allow_html=True)
else:
    st.markdown(f"<div class='status'><span class='yellow'><b>● DATA WAITING</b></span> • Dhan configured: {'YES' if dhan_ok else 'NO'} • {d.get('reason','Waiting for market data')} • stocks {evaln}/500 • sectors {sm}/500 mapped / {sp}/500 priced</div>",unsafe_allow_html=True)
st.markdown("<div class='grid4'>"+"".join([card("🟢 BUY GATE","PASS ✓" if buy else "WAIT"),card("🔴 SELL GATE","PASS ✓" if sell else "WAIT"),card("📡 DATA",f"Dhan {evaln}/500"),card("🔄 REFRESH","15 sec")])+"</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>📚 Previous Close — Reference Only</div>",unsafe_allow_html=True)
pc=d.get("nifty500_previous_close")
st.markdown("<div class='grid4'>"+"".join([card("NIFTY 500 CLOSE",f"{float(pc):,.2f}" if pc is not None else "—"),card("A/D PREVIOUS DAY","Stored after EOD"),card("ADVANCES / DECLINES",f"{d.get('advances','—')} / {d.get('declines','—')}"),card("SECTOR ALIGNMENT",pct(sec)),card("POSITIVE SECTORS",d.get('positive_sectors','—')),card("NEGATIVE SECTORS",d.get('negative_sectors','—')),card("500-STOCK COVERAGE",f"{evaln}/500"),card("SOURCE / DATE",f"Dhan • {now.date()}")])+"</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🔒 Fixed Paper-Trading Rules</div>",unsafe_allow_html=True)
st.markdown("<div class='grid6'>"+"".join([card("CAPITAL / TRADE","₹250,000"),card("RISK / TRADE","₹1,400–₹1,500"),card("TARGET / TRADE","1.25R"),card("MAX TRADES / STRATEGY","1 / day"),card("DAILY LOSS / TRADE","₹1,500"),card("REFRESH","15 sec")])+"</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🔥 All 5 Strategies — One-Glance Board</div>",unsafe_allow_html=True)
st.markdown("<div class='grid2'>"+"".join([f"<div class='strategy'><h4>{s} • {'🟢 ELIGIBLE' if (buy or sell) else '⚪ WAITING'}</h4><div class='muted'>{name}</div><p>1 trade/day • Risk ₹1,400–₹1,500 • Target 1.25R</p></div>" for s,name in STRATEGIES.items()])+"</div>",unsafe_allow_html=True)

trades=read_csv("trades.csv"); signals=read_csv("signals.csv")
if not trades.empty and "strategy" in trades.columns: trades["strategy"]=trades["strategy"].map(norm_strategy)
if not signals.empty:
    if "strategy" in signals.columns: signals["strategy"]=signals["strategy"].map(norm_strategy)
    elif "setup_type" in signals.columns: signals["strategy"]=signals["setup_type"].map(norm_strategy)

st.markdown("<div class='sec'>📊 Three Analysis Records</div>",unsafe_allow_html=True)
t1,t2,t3=st.tabs(["1 · TODAY'S TAKEN TRADES","2 · ACTUAL P&L / DRAWDOWN","3 · ALL ELIGIBLE OPPORTUNITIES"])
with t1:
    today=trades.copy()
    if not today.empty:
        dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
        if dc:
            dt=pd.to_datetime(today[dc],errors="coerce"); today=today[dt.dt.date==now.date()]
    pnl=pd.to_numeric(today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0.0)
    st.markdown("<div class='grid6'>"+"".join([card("TRADES",len(today)),card("WINS",int((pnl>0).sum())),card("LOSSES",int((pnl<0).sum())),card("WIN RATE",f"{(pnl>0).sum()/len(pnl)*100:.1f}%" if len(pnl) else "—"),card("TODAY P&L",money(pnl.sum())),card("TODAY DD",money(drawdown(pnl)))])+"</div>",unsafe_allow_html=True)
    if not today.empty:
        cols=[c for c in ["entry_time","strategy","symbol","signal","entry","stop_loss","target","quantity","actual_risk","exit_time","exit_price","exit_reason","pnl"] if c in today.columns]
        st.dataframe(today[cols] if cols else today,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download Today's Taken Trades",today.to_csv(index=False).encode(),f"today_taken_trades_{now.date()}.csv","text/csv")
    else: st.info("No taken trades recorded today.")
with t2:
    if not trades.empty and "pnl" in trades.columns:
        x=trades.copy(); x["pnl"]=pd.to_numeric(x["pnl"],errors="coerce").fillna(0.0)
        dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in x.columns),None)
        x["Date"]=pd.to_datetime(x[dc],errors="coerce").dt.date if dc else now.date()
        daily=x.groupby("Date",as_index=False)["pnl"].sum().sort_values("Date"); daily["Cumulative P&L"]=daily["pnl"].cumsum(); daily["Peak"]=daily["Cumulative P&L"].cummax(); daily["Drawdown"]=daily["Cumulative P&L"]-daily["Peak"]
        st.markdown("<div class='grid6'>"+"".join([card("TOTAL TRADES",len(x)),card("WINS",int((x.pnl>0).sum())),card("LOSSES",int((x.pnl<0).sum())),card("CUMULATIVE P&L",money(x.pnl.sum())),card("MAX DRAWDOWN",money(daily.Drawdown.min())),card("WIN RATE",f"{(x.pnl>0).mean()*100:.1f}%")])+"</div>",unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1: st.line_chart(daily.set_index("Date")["Cumulative P&L"],height=250)
        with c2: st.bar_chart(daily.set_index("Date")["pnl"],height=250)
        st.dataframe(daily,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download Actual P&L History",daily.to_csv(index=False).encode(),"actual_pnl_daily.csv","text/csv")
    else: st.info("No actual trade history yet. Cumulative P&L and drawdown will populate from taken trades only.")
with t3:
    r=signals.copy()
    if not r.empty and "approved" in r.columns: r=r[r["approved"].astype(str).str.lower().isin(["true","1","yes","approved"])].copy()
    if not r.empty:
        if "candidate_id" in r.columns and "candidate_id" in trades.columns: r["Taken"]=r["candidate_id"].astype(str).isin(set(trades["candidate_id"].astype(str)))
        else: r["Taken"]=False
        oc=next((c for c in ["research_outcome","outcome","result"] if c in r.columns),None)
        out=r[oc].astype(str).str.upper() if oc else pd.Series(dtype=str); wins=int(out.eq("WIN").sum()); losses=int(out.eq("LOSS").sum()); known=wins+losses
        st.markdown("<div class='grid6'>"+"".join([card("ELIGIBLE SIGNALS",len(r)),card("TAKEN",int(r.Taken.sum())),card("NOT TAKEN",int((~r.Taken).sum())),card("RESEARCH WINS",wins),card("RESEARCH LOSSES",losses),card("KNOWN WIN %",f"{wins/known*100:.1f}%" if known else "PENDING")])+"</div>",unsafe_allow_html=True)
        cols=[c for c in ["timestamp","strategy","symbol","signal","entry","stop_loss","target","actual_risk","Taken",oc] if c and c in r.columns]
        st.dataframe(r[cols] if cols else r,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download ALL Eligible Opportunities",r.to_csv(index=False).encode(),"all_eligible_opportunities.csv","text/csv")
    else: st.info("No eligible-opportunity ledger yet. Every qualifying S1–S5 signal will be stored here, whether taken or not.")

st.markdown("<div class='sec'>💼 Current Paper Trades — All Strategies</div>",unsafe_allow_html=True)
st.info("No open paper trades — waiting for complete alignment and an exact OHLC/PDH/PDL setup.")
st.markdown("<div class='sec'>⚙️ Data Status</div>",unsafe_allow_html=True)
st.markdown("<div class='grid4'>"+"".join([card("DHAN CREDENTIALS","READY" if dhan_ok else "NOT CONFIGURED"),card("LIVE STOCK DATA",f"{evaln}/500"),card("SECTOR DATA",f"{sm}/500 mapped • {sp}/500 priced"),card("STATUS",str(d.get('reason','OK'))[:55])])+"</div>",unsafe_allow_html=True)
st.caption("Paper trading only • no real orders • no artificial market or performance values.")
