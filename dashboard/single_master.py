"""NSE Catalyst master dashboard — clean presentation layer."""
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
trades=read_csv("trades.csv");signals=read_csv("signals.csv")
today=trades.copy();dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
if dc and not today.empty:
    dt=pd.to_datetime(today[dc],errors="coerce");today=today[dt.dt.date==now.date()]
pnl=pd.to_numeric(today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0)
# Presentation-only styling: strategy/data logic above is unchanged.
st.markdown("""<style>
.stApp{background:#000!important;color:#F5F7FB!important}.main .block-container{max-width:1180px;padding:.55rem .65rem 1.5rem}
.hero{background:linear-gradient(135deg,#03070c,#07131d,#06262d);border:1px solid #17343b;border-radius:18px;padding:15px 16px;margin-bottom:8px}.hero h1{margin:0;color:#fff;font-size:1.5rem;font-weight:850}.sub{color:#a9bcc5;font-size:.72rem;margin-top:4px}
.live{background:#07151b;border:1px solid #16434a;border-radius:12px;padding:8px 11px;color:#62e7f4;font-size:.78rem;font-weight:750;margin:6px 0}.section{font-size:1rem;font-weight:850;color:#f5f7fb;margin:14px 0 7px}
.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.card{background:#0b1015;border:1px solid #202d36;border-radius:12px;padding:9px;min-height:58px}.label{font-size:.54rem;font-weight:800;color:#8fa1ab;text-transform:uppercase;letter-spacing:.35px}.value{font-size:.9rem;font-weight:850;color:#f5f7fb;margin-top:4px}.good{color:#27df91}.bad{color:#ff5d68}.warn{color:#ffd166}
.strategy{background:#0b1015;border:1px solid #202d36;border-left:3px solid #00d9ff;border-radius:12px;padding:9px 10px;margin:6px 0}.strategy b{font-size:.82rem;color:#f5f7fb}.muted{font-size:.68rem;color:#93a4ad;margin-top:4px}.tip{background:#08191d;border:1px solid #17484e;border-radius:13px;padding:12px;color:#d8f8fa;font-size:.78rem;font-weight:650}.stDownloadButton button{background:#071e24!important;color:#5de7f5!important;border:1px solid #00d9ff!important;border-radius:10px!important;font-weight:800!important}
@media(max-width:850px){.grid6{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.grid6{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:1.25rem}.section{font-size:.94rem}.card{padding:8px}.value{font-size:.84rem}}
</style>""",unsafe_allow_html=True)
# Browser-only clock; it does not rerun the Streamlit dashboard.
st.markdown("""<div class='live'>🕒 <b>LIVE APP TIME • INDIA</b><span id='nse-clock'> --:--:-- IST</span><script>(function(){function t(){var e=document.getElementById('nse-clock');if(e)e.textContent=' '+new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date())+' IST';}t();setInterval(t,15000);})();</script></div>""",unsafe_allow_html=True)
n=market.get("nifty500_change_pct");sec=market.get("sector_alignment_pct");ad=market.get("ad_ratio");evaln=int(market.get("evaluated",0) or 0);sp=int(market.get("sector_priced",0) or 0)
buy=bool(market.get("complete") and market.get("sector_complete") and num(n,0)>0 and num(sec,0)>0 and num(ad,0)>1);sell=bool(market.get("complete") and market.get("sector_complete") and num(n,0)<0 and num(sec,0)<0 and num(ad,2)<1);bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
st.markdown('<div class="hero"><h1>📊 NSE CATALYST</h1><div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan data • S1–S5</div></div>',unsafe_allow_html=True)
last_time=market.get("last_quote_time") or (api_status.get("updated_at") or "—");status_word="RUNNING • Dhan PASS" if dhan_ok and api_status.get("ok") else "RUNNING • WAITING FOR DATA"
st.markdown(f'<div class="live"><b>🟢 {status_word}</b> &nbsp;•&nbsp; Last Dhan data: {last_time} &nbsp;•&nbsp; NSE close: 15:30 IST</div>',unsafe_allow_html=True)
st.markdown('<div class="section">🎯 MASTER MARKET ALIGNMENT</div>',unsafe_allow_html=True)
st.markdown('<div class="grid6">'+''.join([card("NIFTY 500",pct(n)),card("SECTORS",pct(sec)),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "WAITING"),card("BREADTH",f"{evaln}/500"),card("SECTOR DATA",f"{sp}/500"),card("MASTER BIAS",bias)])+'</div>',unsafe_allow_html=True)
st.caption(f"Dhan configured: {'YES' if dhan_ok else 'NO'} • API: {'PASS' if api_status.get('ok') else 'WAIT/ERROR'} • quotes {api_status.get('received',0)}/{api_status.get('requested',0)}")
st.markdown('<div class="section">⚡ S1–S5</div>',unsafe_allow_html=True)
strategies={"S1":"Sweep + Open Reclaim","S2":"Breakout + Retest","S3":"Reverse Sweep + Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
for sid,name in strategies.items():
    st.markdown(f'<div class="strategy"><b>{sid} • {name}</b><div class="muted">One trade per strategy • Signal status shown from the existing journal</div></div>',unsafe_allow_html=True)
st.markdown('<div class="section">💰 TODAY\'S ACTUAL TRADING</div>',unsafe_allow_html=True)
wins=int((pnl>0).sum());losses=int((pnl<0).sum());wr=f"{wins/len(pnl)*100:.1f}%" if len(pnl) else "—"
st.markdown('<div class="grid6">'+''.join([card("TRADES",len(today)),card("WINS",wins),card("LOSSES",losses),card("WIN RATE",wr),card("TODAY P&L",f"₹{pnl.sum():,.0f}"),card("TODAY DD",f"₹{min(0,pnl.cumsum().min()) if len(pnl) else 0:,.0f}")])+'</div>',unsafe_allow_html=True)
if not today.empty:st.dataframe(today,width="stretch",hide_index=True)
else:st.info("No taken trades recorded today.")
st.markdown('<div class="section">📥 TRADE CSV DOWNLOADS</div>',unsafe_allow_html=True)
all_csv=trades.to_csv(index=False).encode("utf-8");today_csv=today.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download ALL Daily Trade Details CSV",all_csv,"nse_catalyst_all_daily_trades.csv","text/csv",use_container_width=True,key="all_daily_trades")
st.download_button(f"⬇️ Download TODAY Trade Details CSV ({len(today)})",today_csv,f"nse_catalyst_{now.date()}_trades.csv","text/csv",use_container_width=True,key="today_trades")
st.markdown('<div class="section">🧪 ELIGIBLE OPPORTUNITIES</div>',unsafe_allow_html=True)
if not signals.empty:st.dataframe(signals.tail(100),width="stretch",hide_index=True,height=240)
else:st.info("No eligible-opportunity ledger yet.")
st.download_button("⬇️ Download Signal Ledger CSV",signals.to_csv(index=False).encode("utf-8"),"nse_catalyst_signals.csv","text/csv",use_container_width=True,key="signals_csv")
st.markdown('<div class="section">💡 DAILY TRADING TIP</div>',unsafe_allow_html=True)
st.markdown('<div class="tip">Protect capital first. Take the trade only when your complete setup is confirmed — never chase a moving price.</div>',unsafe_allow_html=True)
st.caption("NSE Catalyst • paper trading only")
