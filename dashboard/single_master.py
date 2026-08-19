"""NSE Catalyst master dashboard — stable screen, verified Dhan data."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
now=datetime.now(IST)
def num(x,d=None):
    try:
        v=float(x); return v if pd.notna(v) else d
    except Exception:return d
def pct(x):
    v=num(x); return f"{v:+.2f}%" if v is not None else "—"
def card(label,value):return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'
def read_csv(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()
try:
    from market.nifty500_breadth import BREADTH
    from market.dhan_data import configured as dhan_configured,dhan_status
    market=BREADTH.snapshot(force=False); dhan_ok=dhan_configured(); api_status=dhan_status()
except Exception as exc:
    market={"complete":False,"sector_complete":False,"reason":f"{type(exc).__name__}: {exc}","evaluated":0,"total":500,"quote_rows":pd.DataFrame()};dhan_ok=False;api_status={"ok":False,"stage":"IMPORT","message":str(exc),"received":0,"requested":0}
quotes=market.get("quote_rows",pd.DataFrame());quotes=quotes if isinstance(quotes,pd.DataFrame) else pd.DataFrame(quotes)
if not quotes.empty:
    quotes=quotes.copy();quotes["SessionDate"]=now.date();quotes["ADRatio"]=market.get("ad_ratio");quotes["Advances"]=market.get("advances");quotes["Declines"]=market.get("declines");quotes["SectorAlignmentPct"]=market.get("sector_alignment_pct");quotes["PositiveSectors"]=market.get("positive_sectors");quotes["NegativeSectors"]=market.get("negative_sectors")
master_journal=quotes.copy()
if not master_journal.empty:master_journal.insert(0,"Session",market.get("closed_session_label","Current Dhan session"));master_journal.insert(1,"DataSource","Dhan")
st.markdown("""<style>.block-container{max-width:1450px;padding:.75rem .8rem 2rem}.title{font-size:clamp(1.55rem,4vw,2.5rem);font-weight:900;margin:0 0 3px;color:#f5f7fb}.sub{font-size:.76rem;color:#9fb1ca;margin-bottom:12px}.sec{font-size:1.12rem;font-weight:900;color:#f5f7fb;margin:16px 0 8px}.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.card,.status{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:10px}.card{min-height:61px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}.value{font-size:.96rem;font-weight:850;color:#f5f7fb;margin-top:4px}.status{margin:7px 0;color:#d9e3f1;font-size:.78rem}.good{color:#72e6a0}.warn{color:#ffd166}.bad{color:#ff8585}.muted{color:#9fb1ca;font-size:.75rem;margin-top:5px}.quote-box{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:16px;margin-top:8px;font-size:1rem;font-weight:700;color:#f5f7fb}.quote-author{font-size:.72rem;color:#9fb1ca;margin-top:7px}.live-clock{background:#0b132b;border:1px solid #35547d;border-radius:12px;padding:9px 14px;margin:6px 0 12px;text-align:center;color:#fff}.live-clock-label{font-size:.62rem;font-weight:900;letter-spacing:.8px;color:#9fb1ca}.live-clock-time{font-size:1.35rem;font-weight:900;margin-top:2px}@media(max-width:850px){.grid6{grid-template-columns:repeat(3,1fr)}.grid4{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.grid6,.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}</style>""",unsafe_allow_html=True)
# Lightweight browser clock: updates every 15 seconds without rerunning the dashboard/data.
st.markdown("""<div class='live-clock'><div class='live-clock-label'>🕒 LIVE APP TIME • INDIA</div><div id='nse-live-clock' class='live-clock-time'>--:--:-- IST</div></div><script>(function(){function tick(){var e=document.getElementById('nse-live-clock');if(!e)return;var s=new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date());e.textContent=s+' IST';}tick();setInterval(tick,15000);})();</script>""",unsafe_allow_html=True)
n=market.get("nifty500_change_pct");sec=market.get("sector_alignment_pct");ad=market.get("ad_ratio");evaln=int(market.get("evaluated",0) or 0);sp=int(market.get("sector_priced",0) or 0)
buy=bool(market.get("complete") and market.get("sector_complete") and num(n,0)>0 and num(sec,0)>0 and num(ad,0)>1);sell=bool(market.get("complete") and market.get("sector_complete") and num(n,0)<0 and num(sec,0)<0 and num(ad,2)<1);bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
st.markdown('<div class="title">📊 NSE Catalyst — Master Dashboard</div>',unsafe_allow_html=True);st.markdown(f'<div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan data • App time {now.strftime("%d %b %Y %H:%M:%S")} IST</div>',unsafe_allow_html=True)
last_time=market.get("last_quote_time") or (api_status.get("updated_at") or "—");status_word="RUNNING • Dhan PASS" if dhan_ok and api_status.get("ok") else "RUNNING • WAITING FOR DATA";st.markdown(f'<div class="status"><b>🟢 {status_word}</b> • Last Dhan data: {last_time} • Market session: {market.get("closed_session_label","—")} • NSE close: 15:30 IST</div>',unsafe_allow_html=True)
st.markdown('<div class="sec">🎯 Master Market Alignment</div>',unsafe_allow_html=True);st.markdown('<div class="grid6">'+''.join([card("NIFTY 500",pct(n)),card("SECTORS",pct(sec)),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "WAITING"),card("BREADTH",f"{evaln}/500"),card("SECTOR DATA",f"{sp}/500"),card("MASTER BIAS",bias)])+'</div>',unsafe_allow_html=True);st.markdown(f'<div class="status"><b>Dhan configured: {"YES" if dhan_ok else "NO"}</b> • API: {"PASS" if api_status.get("ok") else "WAIT/ERROR"} • {api_status.get("message","")} • quotes {api_status.get("received",0)}/{api_status.get("requested",0)}</div>',unsafe_allow_html=True)
# The old misleading "What Happened Yesterday?" and verified-quotes/master-journal download blocks are intentionally removed.
trades=read_csv("trades.csv");signals=read_csv("signals.csv");st.markdown('<div class="sec">🧠 Daily Analysis & Journal</div>',unsafe_allow_html=True);st.info("Verified Dhan session data is the source for analysis. No artificial values are generated.");st.markdown('<div class="sec">1 · Today’s Taken Trades</div>',unsafe_allow_html=True);today=trades.copy();dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
if dc and not today.empty:
    dt=pd.to_datetime(today[dc],errors="coerce");today=today[dt.dt.date==now.date()]
pnl=pd.to_numeric(today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0);win_rate=f"{(pnl>0).mean()*100:.1f}%" if len(pnl) else "—";st.markdown('<div class="grid6">'+''.join([card("TRADES",len(today)),card("WINS",int((pnl>0).sum())),card("LOSSES",int((pnl<0).sum())),card("WIN RATE",win_rate),card("TODAY P&L",f"₹{pnl.sum():,.0f}"),card("TODAY DD",f"₹{min(0,pnl.cumsum().min()) if len(pnl) else 0:,.0f}")])+'</div>',unsafe_allow_html=True)
if not today.empty:st.dataframe(today,width="stretch",hide_index=True)
else:st.info("No taken trades recorded today.")
st.markdown('<div class="sec">2 · Actual P&L / Drawdown</div>',unsafe_allow_html=True)
if trades.empty:st.info("No actual trade history yet.")
else:st.dataframe(trades,width="stretch",hide_index=True)
st.markdown('<div class="sec">3 · All Eligible Opportunities</div>',unsafe_allow_html=True)
if signals.empty:st.info("No eligible-opportunity ledger yet.")
else:st.dataframe(signals,width="stretch",hide_index=True)
st.caption("NSE Catalyst • paper trading only")
