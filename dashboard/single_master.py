"""Single-page NSE Catalyst dashboard with separate live and closed-session data."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata")
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
now=datetime.now(IST)

# IMPORTANT: no Dhan/network call happens during normal page load.
# The user explicitly requests a data refresh, so the screen cannot sit buffering.
if "dhan_refresh_requested" not in st.session_state: st.session_state.dhan_refresh_requested=False
st.markdown("<div class='title'>📊 NSE Catalyst — Master Dashboard</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 • Dhan data • screen does not auto-refresh • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)
if st.button("🔄 Refresh Dhan Data",type="primary",key="refresh_dhan_data"):
    st.session_state.dhan_refresh_requested=True
    st.rerun()

try:
    from market.nifty500_breadth import BREADTH
    from market.dhan_data import configured as dhan_configured, dhan_status
    dhan_ok=dhan_configured(); api_status=dhan_status()
    if st.session_state.dhan_refresh_requested:
        live_market=BREADTH.snapshot(force=True)
    else:
        live_market={"complete":False,"sector_complete":False,"reason":"Press Refresh Dhan Data to request live quotes","evaluated":0,"total":500,"market_data_source":"DHAN"}
except Exception as exc:
    live_market={"complete":False,"sector_complete":False,"reason":f"{type(exc).__name__}: {exc}","evaluated":0,"total":500};dhan_ok=False;api_status={"ok":False,"stage":"IMPORT","message":str(exc),"received":0,"requested":0}

# Closed table reads ONLY the persistent saved snapshot on normal load.
# It contacts Dhan only when the user presses Refresh Dhan Data.
closed_market={};closed_df=pd.DataFrame()
try:
    from market.closed_session import build_closed_snapshot, load_saved, latest_saved_before
    saved_df,saved_summary=latest_saved_before(now.date()) if not st.session_state.dhan_refresh_requested else (pd.DataFrame(),{})
    if not st.session_state.dhan_refresh_requested and not saved_df.empty:
        closed_df,closed_market=saved_df,saved_summary
    elif st.session_state.dhan_refresh_requested:
        closed_df,closed_market=build_closed_snapshot(force=True)
except Exception as exc:
    closed_market={"complete":False,"reason":f"Closed table: {type(exc).__name__}: {exc}"}

# After a manual refresh, reset the flag so subsequent navigation/loading is instant.
if st.session_state.dhan_refresh_requested:
    st.session_state.dhan_refresh_requested=False

if closed_market.get("complete") and len(closed_df)>0:
    market={"complete":len(closed_df)>=450,"sector_complete":closed_market.get("sector_alignment_pct") is not None,"evaluated":len(closed_df),"total":500,"advances":closed_market.get("advances",0),"declines":closed_market.get("declines",0),"ad_ratio":closed_market.get("ad_ratio"),"nifty500_change_pct":closed_market.get("nifty500_change_pct"),"nifty500_previous_close":closed_market.get("nifty500_close"),"sector_alignment_pct":closed_market.get("sector_alignment_pct"),"sector_priced":len(closed_df),"positive_sectors":closed_market.get("positive_sectors",0),"negative_sectors":closed_market.get("negative_sectors",0),"updated_at":f"Completed session {closed_market.get('session_date','')} • market close 15:30 IST • saved {closed_market.get('saved_at','')}","closed_session_label":f"Completed NSE session • {closed_market.get('session_date','')}","closed_session_basis":"Persistent Dhan completed-session table","market_data_source":"DHAN CLOSED TABLE"}
    api_status=closed_market.get("dhan_status",api_status)
else: market=live_market

def read_csv(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()
def num(x,default=None):
 try:return float(x)
 except Exception:return default
def money(x):return f"₹{num(x,0):,.0f}"
def pct(x):
 v=num(x);return f"{v:+.2f}%" if v is not None else "—"
def card(label,value):return f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"
def strategy_name(x):
 s=str(x).upper().strip();return s if s in STRATEGIES else ("S"+s.split("_")[-1] if s.startswith("STRATEGY_") else s)
def max_dd(series):
 if series is None or len(series)==0:return 0.0
 s=pd.to_numeric(series,errors="coerce").fillna(0.0);eq=s.cumsum();return float((eq-eq.cummax()).min())

st.markdown("""<style>.block-container{max-width:1450px;padding:.75rem .8rem 2rem}.title{font-size:clamp(1.55rem,4vw,2.5rem);font-weight:900;color:#f5f7fb}.sub{font-size:.76rem;color:#9fb1ca;margin-bottom:12px}.sec{font-size:1.12rem;font-weight:900;color:#f5f7fb;margin:16px 0 8px}.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.card,.status,.strategy{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:9px}.card{min-height:61px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}.value{font-size:.96rem;font-weight:850;color:#f5f7fb;margin-top:4px}.status{margin:7px 0;color:#d9e3f1;font-size:.78rem}.ok{color:#42d17a}.wait{color:#ffd166}.strategy{min-height:95px}.strategy b{font-size:.98rem}.muted{color:#9fb1ca;font-size:.75rem;margin-top:5px}@media(max-width:850px){.grid6{grid-template-columns:repeat(3,1fr)}.grid4{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.grid6,.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}</style>""",unsafe_allow_html=True)

n=market.get("nifty500_change_pct");sec=market.get("sector_alignment_pct");ad=market.get("ad_ratio");evaln=int(market.get("evaluated",0) or 0);sp=int(market.get("sector_priced",0) or 0);complete=bool(market.get("complete"));scomplete=bool(market.get("sector_complete"));buy=complete and scomplete and num(n) is not None and num(sec) is not None and num(ad) is not None and n>0 and sec>0 and ad>1;sell=complete and scomplete and num(n) is not None and num(sec) is not None and num(ad) is not None and n<0 and sec<0 and ad<1;bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
st.markdown("<div class='sec'>🎯 Master Market Alignment</div>",unsafe_allow_html=True);st.markdown("<div class='grid6'>"+"".join([card("NIFTY 500",pct(n)),card("SECTORS",pct(sec)),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "WAITING"),card("BREADTH",f"{evaln}/500"),card("SECTOR DATA",f"{sp}/500"),card("MASTER BIAS",bias)])+"</div>",unsafe_allow_html=True)
st.markdown(f"<div class='status'><b>Dhan:</b> {'CONFIGURED' if dhan_ok else 'NOT CONFIGURED'} • <b>API:</b> {api_status.get('stage','NOT TESTED')} • {api_status.get('message','Press Refresh Dhan Data to test')} • quotes {api_status.get('received',0)}/{api_status.get('requested',0)}</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>📚 Previous / Latest Closed Session — Separate Table</div>",unsafe_allow_html=True);pc=market.get("nifty500_previous_close");st.markdown("<div class='grid4'>"+"".join([card("NIFTY 500 CLOSE",f"{pc:,.2f}" if pc is not None else "—"),card("A/D RATIO",f"{ad:.2f}" if ad is not None else "—"),card("ADVANCES / DECLINES",f"{market.get('advances','—')} / {market.get('declines','—')}"),card("SECTOR ALIGNMENT",pct(sec)),card("POSITIVE SECTORS",market.get('positive_sectors','—')),card("NEGATIVE SECTORS",market.get('negative_sectors','—')),card("500-STOCK COVERAGE",f"{evaln}/500"),card("SESSION",market.get('closed_session_label','No saved completed session'))])+"</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🔎 What Happened Yesterday?</div>",unsafe_allow_html=True);st.markdown(f"<div class='status'><b>{market.get('closed_session_label','No saved completed session')}</b> • Close: {f'{pc:,.2f}' if pc is not None else '—'} • Change: {pct(n)} • A/D: {f'{ad:.2f}' if ad is not None else '—'} • Advances/Declines: {market.get('advances','—')}/{market.get('declines','—')} • Sector alignment: {pct(sec)}</div>",unsafe_allow_html=True)

trades=read_csv("trades.csv");signals=read_csv("signals.csv")
if not trades.empty and "strategy" in trades.columns:trades["strategy"]=trades["strategy"].map(strategy_name)
if not signals.empty and "strategy" in signals.columns:signals["strategy"]=signals["strategy"].map(strategy_name)
st.markdown("<div class='sec'>🧠 Daily Analysis & Journal</div>",unsafe_allow_html=True)
if complete:
 conclusion="Bullish breadth" if num(ad) is not None and ad>1 and num(n) is not None and n>0 else "Bearish breadth" if num(ad) is not None and ad<1 and num(n) is not None and n<0 else "Mixed/neutral breadth";st.markdown(f"<div class='status'><b>Session conclusion:</b> {conclusion}. Derived from saved Dhan values only.</div>",unsafe_allow_html=True)
else:st.info("Press 'Refresh Dhan Data' to retrieve current/completed Dhan data. Saved closed data remains independent.")

st.markdown("<div class='sec'>1 · Today's Taken Trades</div>",unsafe_allow_html=True);today=trades.copy();dc=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
if dc and not today.empty:
 dt=pd.to_datetime(today[dc],errors="coerce");today=today[dt.dt.date==now.date()]
pnl=pd.to_numeric(today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0);st.markdown("<div class='grid6'>"+"".join([card("TRADES",len(today)),card("WINS",int((pnl>0).sum())),card("LOSSES",int((pnl<0).sum())),card("WIN RATE",f"{(pnl>0).mean()*100:.1f}%" if len(pnl) else "—"),card("TODAY P&L",money(pnl.sum())),card("TODAY DD",money(max_dd(pnl)))])+"</div>",unsafe_allow_html=True)
if not today.empty:st.dataframe(today,width="stretch",hide_index=True);st.download_button("⬇️ CSV — Today's Taken Trades",today.to_csv(index=False).encode(),f"today_taken_{now.date()}.csv","text/csv")
else:st.info("No taken trades recorded today.")

st.markdown("<div class='sec'>⚖️ S1–S5 Strategy Comparison</div>",unsafe_allow_html=True)
rows=[]
for s,name in STRATEGIES.items():
 t=trades[trades["strategy"].astype(str).eq(s)].copy() if not trades.empty and "strategy" in trades.columns else pd.DataFrame();pnlc="pnl" if "pnl" in t.columns else None;p=pd.to_numeric(t[pnlc],errors="coerce").dropna() if pnlc else pd.Series(dtype=float);rows.append({"Strategy":s,"Name":name,"Taken":len(t),"Wins":int((p>0).sum()),"Losses":int((p<0).sum()),"Win %":round((p>0).mean()*100,1) if len(p) else None,"P&L":p.sum() if len(p) else 0})
st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)

st.caption("NSE Catalyst • paper trading only • no real orders • screen does not auto-refresh")
