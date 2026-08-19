"""Clean analysis center: actual trades versus all eligible research opportunities."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
STRATEGIES = {"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}

st.set_page_config(page_title="Analysis | NSE Catalyst", page_icon="📈", layout="wide")
st.markdown("""
<style>
html,body,[class*="css"]{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
.block-container{max-width:1450px;padding:1.1rem .9rem 2rem}
.title{font-size:clamp(1.8rem,4vw,2.7rem);font-weight:900;color:#f4f7fb;margin-bottom:4px}.sub{color:#9fb1ca;font-size:.88rem;margin-bottom:18px}
.sec{font-size:1.25rem;font-weight:850;margin:20px 0 10px;color:#f4f7fb}.note{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:12px 14px;color:#dbe6f5;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px}.card{border:1px solid #2b4163;background:linear-gradient(145deg,#111b2b,#0f1928);border-radius:13px;padding:12px;min-height:78px}.card small{color:#9fb1ca;font-size:.64rem;font-weight:800;text-transform:uppercase}.card b{display:block;color:#f4f7fb;font-size:1.12rem;margin-top:6px}
@media(max-width:900px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:600px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.title{font-size:1.65rem}.sec{font-size:1.1rem}}
</style>
""", unsafe_allow_html=True)

def read_csv(name):
    p = ROOT / "outputs" / name
    try: return pd.read_csv(p)
    except Exception: return pd.DataFrame()

def money(v):
    try: return f"₹{float(v):,.0f}"
    except Exception: return "—"

def card(label, value):
    return f"<div class='card'><small>{label}</small><b>{value}</b></div>"

def norm_strategy(v):
    s = str(v).upper().strip()
    if s in STRATEGIES: return s
    if s.startswith("STRATEGY_"): return "S" + s.split("_")[-1]
    return s

def closed_trades(df):
    if df.empty: return df
    d = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy() if "status" in df.columns else df.copy()
    if "pnl" in d.columns: d["pnl"] = pd.to_numeric(d["pnl"], errors="coerce").fillna(0.0)
    return d

def drawdown(series):
    if series.empty: return 0.0
    equity = series.cumsum()
    return float((equity - equity.cummax()).min())

def strategy_stats(df):
    rows=[]
    for s in STRATEGIES:
        d=df[df["strategy"].eq(s)] if not df.empty and "strategy" in df.columns else pd.DataFrame()
        pnl=pd.to_numeric(d.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0.0)
        wins=int((pnl>0).sum()); losses=int((pnl<0).sum()); total=len(pnl)
        gross_win=float(pnl[pnl>0].sum()); gross_loss=abs(float(pnl[pnl<0].sum()))
        rows.append({"Strategy":s,"Opportunities":total,"Wins":wins,"Losses":losses,"Win %":round(wins/total*100,1) if total else 0,"Net P&L":round(float(pnl.sum()),2),"Max DD":round(drawdown(pnl),2),"Profit Factor":round(gross_win/gross_loss,2) if gross_loss else (999 if gross_win else 0)})
    return pd.DataFrame(rows)

now=datetime.now(IST)
trades=read_csv("trades.csv")
signals=read_csv("signals.csv")
if not trades.empty:
    trade_strategy = trades["strategy"] if "strategy" in trades.columns else pd.Series([""]*len(trades),index=trades.index)
    trades["strategy"] = trade_strategy.map(norm_strategy)
    trades=closed_trades(trades)
if not signals.empty:
    signal_strategy = signals["strategy"] if "strategy" in signals.columns else (signals["setup_type"] if "setup_type" in signals.columns else pd.Series([""]*len(signals),index=signals.index))
    signals["strategy"] = signal_strategy.map(norm_strategy)
    if "approved" in signals.columns:
        approved=signals[signals["approved"].astype(str).str.lower().isin(["true","1","yes","approved"])].copy()
    else: approved=signals.copy()
else: approved=pd.DataFrame()

st.markdown("<div class='title'>📈 NSE Catalyst — Analysis Center</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>Two permanent analysis views • actual trades are kept separate from all eligible opportunities • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)
actual_tab, research_tab = st.tabs(["1 · TODAY / ACTUAL TRADING", "2 · ALL OPPORTUNITIES / RESEARCH"])

with actual_tab:
    st.markdown("<div class='sec'>📋 Today's Actual Trades</div>",unsafe_allow_html=True)
    today=trades.copy()
    if not today.empty:
        date_col=next((c for c in ["exit_time","entry_time","timestamp"] if c in today.columns),None)
        if date_col:
            dt=pd.to_datetime(today[date_col],errors="coerce")
            today=today[dt.dt.date==now.date()]
    pnl=pd.to_numeric(today.get("pnl",pd.Series(dtype=float)),errors="coerce").fillna(0.0)
    wins=int((pnl>0).sum()); losses=int((pnl<0).sum())
    st.markdown("<div class='grid'>"+"".join([card("TRADES",len(today)),card("WINS",wins),card("LOSSES",losses),card("WIN RATE",f"{wins/len(pnl)*100:.1f}%" if len(pnl) else "—"),card("TODAY P&L",money(pnl.sum())),card("TODAY DRAW DOWN",money(drawdown(pnl)))])+"</div>",unsafe_allow_html=True)
    if not today.empty:
        show=[c for c in ["entry_time","strategy","symbol","signal","entry","stop_loss","target","quantity","actual_risk","exit_time","exit_price","exit_reason","pnl","nifty500_change_pct","sector","setup_type"] if c in today.columns]
        st.dataframe(today[show] if show else today,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download Today's Actual Trades CSV",today.to_csv(index=False).encode(),f"actual_trades_{now.date()}.csv","text/csv")
    else: st.info("No closed actual trades recorded today.")
    st.markdown("<div class='note'><b>Actual account view:</b> this tab uses only trades actually taken. It never mixes untraded signals into your account P&L.</div>",unsafe_allow_html=True)

with research_tab:
    st.markdown("<div class='sec'>🧪 All Eligible Opportunities</div>",unsafe_allow_html=True)
    if not approved.empty:
        trade_ids=set(trades["candidate_id"].astype(str)) if "candidate_id" in trades.columns else set()
        approved["Taken"] = approved["candidate_id"].astype(str).isin(trade_ids) if "candidate_id" in approved.columns else False
        if "research_outcome" not in approved.columns: approved["research_outcome"]="PENDING"
        outcome=approved["research_outcome"].astype(str).str.upper()
        wins=int(outcome.eq("WIN").sum()); losses=int(outcome.eq("LOSS").sum()); known=wins+losses
        st.markdown("<div class='grid'>"+"".join([card("ELIGIBLE",len(approved)),card("TAKEN",int(approved["Taken"].sum())),card("NOT TAKEN",int((~approved["Taken"]).sum())),card("RESEARCH WINS",wins),card("RESEARCH LOSSES",losses),card("KNOWN WIN %",f"{wins/known*100:.1f}%" if known else "PENDING")])+"</div>",unsafe_allow_html=True)
        stats=strategy_stats(approved)
        st.markdown("### 🏆 Strategy Research")
        st.dataframe(stats,use_container_width=True,hide_index=True)
        a,b=st.columns(2)
        with a: st.plotly_chart(px.bar(stats,x="Strategy",y="Opportunities",title="Eligible Opportunities",text_auto=True),use_container_width=True)
        with b: st.plotly_chart(px.bar(stats,x="Strategy",y="Win %",title="Research Win Rate",text_auto=".1f"),use_container_width=True)
        if not trades.empty and "exit_time" in trades.columns:
            td=trades.copy();td["Date"]=pd.to_datetime(td["exit_time"],errors="coerce").dt.date;daily=td.groupby("Date",as_index=False)["pnl"].sum();daily["Cumulative P&L"]=daily["pnl"].cumsum()
            a,b=st.columns(2)
            with a: st.plotly_chart(px.bar(daily,x="Date",y="pnl",title="Actual Daily P&L",text_auto=True),use_container_width=True)
            with b: st.plotly_chart(px.line(daily,x="Date",y="Cumulative P&L",title="Actual Cumulative P&L",markers=True),use_container_width=True)
        st.download_button("⬇️ Download All Eligible Opportunities CSV",approved.to_csv(index=False).encode(),"all_eligible_opportunities.csv","text/csv")
        st.markdown("<div class='note'><b>Research rule:</b> every eligible signal is stored separately from actual trades. A research WIN/LOSS is counted only after a subsequent price path proves target or SL; pending signals are not treated as wins or losses.</div>",unsafe_allow_html=True)
    else:
        st.markdown("<div class='grid'>"+"".join([card("ELIGIBLE",0),card("TAKEN",0),card("NOT TAKEN",0),card("RESEARCH WINS",0),card("RESEARCH LOSSES",0),card("KNOWN WIN %","PENDING")])+"</div>",unsafe_allow_html=True)
        st.info("No approved opportunity history is available yet. The research ledger will populate when S1–S5 record eligible signals.")

st.markdown("<div class='sec'>📦 Data Downloads</div>",unsafe_allow_html=True)
for name,label in [("trades.csv","Actual trades"),("signals.csv","All scanner signals"),("MASTER_TRADES.csv","Master trades"),("MASTER_DAILY_SUMMARY.csv","Daily master summary")]:
    p=ROOT/"outputs"/name
    if p.exists(): st.download_button(f"⬇️ {label}",p.read_bytes(),name,"text/csv",key=f"dl_{name}")
st.caption("Paper trading only • No real orders • Research results are based only on recorded market outcomes; no artificial win rates are generated.")
