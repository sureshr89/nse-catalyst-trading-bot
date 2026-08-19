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
st.markdown("""<style>.block-container{max-width:1450px;padding:.75rem .8rem 2rem}.title{font-size:clamp(1.55rem,4vw,2.5rem);font-weight:900;margin:0 0 3px;color:#f5f7fb}.sub{font-size:.76rem;color:#9fb1ca;margin-bottom:12px}.sec{font-size:1.12rem;font-weight:900;color:#f5f7fb;margin:16px 0 8px}.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.card,.status{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:10px}.card{min-height:61px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}.value{font-size:.96rem;font-weight:850;color:#f5f7fb;margin-top:4px}.status{margin:7px 0;color:#d9e3f1;font-size:.78rem}.good{color:#72e6a0}.warn{color:#ffd166}.bad{color:#ff8585}.muted{color:#9fb1ca;font-size:.75rem;margin-top:5px}.quote-box{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:16px;margin-top:8px;font-size:1rem;font-weight:700;color:#f5f7fb}.quote-author{font-size:.72rem;color:#9fb1ca;margin-top:7px}@media(max-width:850px){.grid6{grid-template-columns:repeat(3,1fr)}.grid4{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.grid6,.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}</style>""",unsafe_allow_html=True)
n=market.get("nifty500_change_pct");sec=market.get("sector_alignment_pct");ad=market.get("ad_ratio");evaln=int(market.get("evaluated",0) or 0);sp=int(market.get("sector_priced",0) or 0)
buy=bool(market.get("complete") and market.get("sector_complete") and num(n,0)>0 and num(sec,0)>0 and num(ad,0)>1);sell=bool(market.get("complete") and market.get("sector_complete") and num(n,0)<0 and num(sec,0)<0 and num(ad,2)<1);bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
st.markdown('<div class="title">📊 NSE Catalyst — Master Dashboard</div>',unsafe_allow_html=True);st.markdown(f'<div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan data • no automatic screen refresh • App time {now.strftime("%d %b %Y %H:%M:%S")} IST</div>',unsafe_allow_html=True)
last_time=market.get("last_quote_time") or (api_status.get("updated_at") or "—");status_word="RUNNING • Dhan PASS" if dhan_ok and api_status.get("ok") else "RUNNING • WAITING FOR DATA";st.markdown(f'<div class="status"><b>🟢 {status_word}</b> • App time: {now.strftime("%H:%M:%S")} IST • Last Dhan data: {last_time} • Market session: {market.get("closed_session_label","—")} • NSE close: 15:30 IST</div>',unsafe_allow_html=True)
st.markdown('<div class="sec">🎯 Master Market Alignment</div>',unsafe_allow_html=True);st.markdown('<div class="grid6">'+''.join([card("NIFTY 500",pct(n)),card("SECTORS",pct(sec)),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "WAITING"),card("BREADTH",f"{evaln}/500"),card("SECTOR DATA",f"{sp}/500"),card("MASTER BIAS",bias)])+'</div>',unsafe_allow_html=True);st.markdown(f'<div class="status"><b>Dhan configured: {"YES" if dhan_ok else "NO"}</b> • API: {"PASS" if api_status.get("ok") else "WAIT/ERROR"} • {api_status.get("message","")} • quotes {api_status.get("received",0)}/{api_status.get("requested",0)}</div>',unsafe_allow_html=True)
st.markdown('<div class="sec">🔎 What Happened Yesterday?</div>',unsafe_allow_html=True);close=num(market.get("nifty500_previous_close"));close_text=f"{close:,.2f}" if close is not None else "—";st.markdown(f'<div class="grid4">'+''.join([card("NIFTY 500 CLOSE",close_text),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "—"),card("ADVANCES / DECLINES",f"{market.get("advances","—")} / {market.get("declines","—")}"),card("SECTOR ALIGNMENT",pct(sec))])+'</div>',unsafe_allow_html=True);st.markdown(f'<div class="grid4">'+''.join([card("POSITIVE SECTORS",market.get("positive_sectors","—")),card("NEGATIVE SECTORS",market.get("negative_sectors","—")),card("500-STOCK COVERAGE",f"{evaln}/500"),card("DATA SOURCE / TIME",f"Dhan • {market.get("closed_session_label","—")} • 15:30 IST")])+'</div>',unsafe_allow_html=True)
if not market.get("sector_complete"):
    err=market.get("sector_error") or "Sector mapping is not yet verified for all 500 stocks.";st.warning(f"Sector data: {err}")
st.markdown('<div class="sec">📋 Dhan Quotes — Verified Prices</div>',unsafe_allow_html=True)
if quotes.empty:st.info("No verified Dhan quote rows are available in this run.")
else:
    show=[c for c in ["Symbol","SecurityId","LTP","TodayOpen","TodayHigh","TodayLow","TodayClose","PreviousClose","NetChange","Volume","change_pct"] if c in quotes.columns];st.caption(f"Verified price rows: {len(quotes)}/500 • Last data: {last_time}");st.dataframe(quotes[show].head(20),width="stretch",hide_index=True);st.download_button("⬇️ Download all 500 Dhan Quotes CSV",quotes.to_csv(index=False).encode(),f"nifty500_dhan_quotes_{now.date()}.csv","text/csv")
st.markdown('<div class="sec">📘 Master Journal — Download</div>',unsafe_allow_html=True)
if master_journal.empty:st.info("Master Journal will appear when the verified 500-stock Dhan dataset is available.")
else:st.caption(f"Master Journal ready: {len(master_journal)}/500 verified Dhan rows • session {market.get('closed_session_label','Current session')}");st.download_button("⬇️ Download Master Journal CSV",master_journal.to_csv(index=False).encode(),f"nse_catalyst_master_journal_{now.date()}.csv","text/csv")
trades=read_csv("trades.csv");signals=read_csv("signals.csv");st.markdown('<div class="sec">🧠 Daily Analysis & Journal</div>',unsafe_allow_html=True);st.info("Verified Dhan session data is the source for the master journal. No artificial values are generated.");st.markdown('<div class="sec">1 · Today’s Taken Trades</div>',unsafe_allow_html=True);today=trades.copy();dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
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
DAILY_QUOTES=["Protect your capital first; opportunities come again.","A good trade is planned before it is entered.","Discipline turns a strategy into an edge.","Wait for confirmation; missing a trade is cheaper than forcing one.","Trade the setup, not the emotion.","Consistency matters more than one big win.","Risk small enough to stay in the game.","Patience is a trading skill, not inactivity.","Your stop-loss is part of the strategy, not a failure.","Let price confirm your idea before you commit capital."]
quote=DAILY_QUOTES[(now.date().toordinal())%len(DAILY_QUOTES)]
st.markdown('<div class="sec">💡 Daily Trading Quote</div>',unsafe_allow_html=True);st.markdown(f'<div class="quote-box">“{quote}”<div class="quote-author">Daily trading tip • {now.strftime("%d %b %Y")}</div></div>',unsafe_allow_html=True)
st.caption("NSE Catalyst • paper trading only • no automatic screen refresh")
