"""Single combined NSE Catalyst dashboard for S1-S5 paper trading."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

ROOT=Path(__file__).resolve().parents[1]; IST=ZoneInfo("Asia/Kolkata"); REFRESH=15
CAPITAL=250000; MIN_RISK=1400; MAX_RISK=1500; RR=1.25; MAX_TRADES=1; DAILY_LOSS=1500
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
QUOTES=["Process first. Profit follows disciplined execution.","Protect capital, wait for alignment, then act.","A good trade is a rule-following trade, not just a winning trade.","Consistency comes from repeating a tested process.","No setup is also a valid decision.","Risk is fixed before the entry; everything else follows."]

st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=REFRESH*1000,key="master_refresh")
st.markdown("""
<style>
.title{font-size:2.05rem;font-weight:900}.sub{color:#9eb0c8;margin-bottom:16px}.sec{font-size:1.18rem;font-weight:850;margin:22px 0 10px}.card{border:1px solid #2e405d;background:#111a29;border-radius:13px;padding:13px;min-height:88px}.card small{display:block;color:#93a6bf;font-weight:750;text-transform:uppercase}.card b{font-size:1.35rem;display:block;margin-top:5px}.strategy{border:1px solid #2e405d;background:#111a29;border-radius:13px;padding:12px;min-height:130px}.strategy h4{margin:0 0 7px}.muted{color:#9eb0c8}.quote{border-left:4px solid #6686b0;background:#111a29;padding:13px 16px;border-radius:8px;font-style:italic}
</style>""",unsafe_allow_html=True)

def load_json(name):
    p=ROOT/"outputs"/name
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return {}

def load_csv(name):
    p=ROOT/"outputs"/name
    try:return pd.read_csv(p)
    except Exception:return pd.DataFrame()

def money(v):
    try:return f"₹{float(v):,.0f}"
    except:return "—"

def pct(v):
    try:return f"{float(v):+.2f}%"
    except:return "—"

def k(label,value,cls=""):
    return f"<div class='card'><small>{label}</small><b class='{cls}'>{value}</b></div>"

def normalize_strategy(v):
    s=str(v).upper().strip()
    if s in STRATEGIES:return s
    if s.startswith("STRATEGY_"):return "S"+s.split("_")[-1]
    if s=="OPEN_RETURN":return "S1"
    return s

now=datetime.now(IST);diag=load_json("scanner_diagnostics.json");state=load_json("paper_engine_state.json");trades=load_csv("trades.csv")
if not trades.empty:
    if "strategy" not in trades.columns:trades["strategy"]=""
    trades["strategy"]=trades["strategy"].map(normalize_strategy)
    if "pnl" in trades:trades["pnl"]=pd.to_numeric(trades["pnl"],errors="coerce").fillna(0)

nifty=diag.get("nifty500_change_pct");sector=diag.get("sector_change_pct");ad=diag.get("ad_ratio")
coverage=str(diag.get("ad_coverage","0/500"));priced=str(diag.get("market_data_coverage","0/500"));sector_map=str(diag.get("sector_mapping","0/500"));sector_priced=str(diag.get("sector_priced","0/500"))
full_breadth=coverage=="500/500";sector_ok=bool(diag.get("sector_available")) and sector_map=="500/500" and sector_priced=="500/500";buy=bool(diag.get("buy_alignment"));sell=bool(diag.get("sell_alignment"));bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

st.markdown("<div class='title'>📊 NSE Catalyst — Master Dashboard</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 combined • PAPER TRADING ONLY • refresh every {REFRESH}s • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)
st.markdown("<div class='sec'>🎯 Master Market Alignment</div>",unsafe_allow_html=True)
st.markdown("<div style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px'>"+"".join([k("NIFTY 500",pct(nifty)),k("SECTOR ALIGNMENT",pct(sector)),k("NIFTY 500 A/D",f"{float(ad):.2f}" if full_breadth and ad is not None else "UNAVAILABLE"),k("A/D COVERAGE",coverage),k("SECTOR COVERAGE",sector_priced),k("MASTER BIAS",bias)])+"</div>",unsafe_allow_html=True)
if not full_breadth:st.error(f"🚫 TRADING BLOCKED — NIFTY 500 breadth is {coverage}. Full 500/500 is mandatory.")
if not sector_ok:st.error(f"🚫 TRADING BLOCKED — sector integrity is incomplete. Mapping {sector_map}; priced {sector_priced}.")

st.markdown("<div class='sec'>🔒 Fixed Paper-Trading Rules</div>",unsafe_allow_html=True)
st.markdown("<div style='display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px'>"+"".join([k("CAPITAL / TRADE","₹2,50,000"),k("RISK / TRADE","₹1,400–₹1,500"),k("TARGET","1.25R"),k("MAX TRADES / STRATEGY","1 / day"),k("MAX DAILY LOSS","₹1,500 / strategy"),k("REFRESH","15 sec")])+"</div>",unsafe_allow_html=True)
st.caption("Position size is calculated from actual Entry→SL distance. If actual risk is outside ₹1,400–₹1,500, the trade is rejected. No live orders are permitted.")

st.markdown("<div class='sec'>🔥 All 5 Strategies — One-Glance Board</div>",unsafe_allow_html=True);cols=st.columns(5)
for col,s in zip(cols,STRATEGIES):
    with col:
        td=trades[trades["strategy"]==s] if not trades.empty else pd.DataFrame();today_td=td
        if not td.empty and "entry_time" in td.columns:
            dt=pd.to_datetime(td["entry_time"],errors="coerce");today_td=td[dt.dt.date==now.date()]
        wins=int((today_td["pnl"]>0).sum()) if not today_td.empty and "pnl" in today_td else 0;losses=int((today_td["pnl"]<0).sum()) if not today_td.empty and "pnl" in today_td else 0;pnl=float(today_td["pnl"].sum()) if not today_td.empty and "pnl" in today_td else 0;locked=len(today_td)>=MAX_TRADES or pnl<=-DAILY_LOSS;status="🔒 LOCKED" if locked else "🟢 ALIGNED" if (buy or sell) else "⚪ WAITING"
        st.markdown(f"<div class='strategy'><h4>{s} • {status}</h4><div class='muted'>{STRATEGIES[s]}</div><br>Trades <b>{len(today_td)}/{MAX_TRADES}</b> • Wins <b>{wins}</b> • Losses <b>{losses}</b><br>Daily P&L <b>{money(pnl)}</b></div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>💼 Current Paper Trades — All Strategies</div>",unsafe_allow_html=True);open_positions=state.get("open_positions",{}) if isinstance(state,dict) else {}
if open_positions:
    rows=[]
    for symbol,p in open_positions.items():
        ltp=p.get("last_live_price",p.get("entry"));side=p.get("signal","—");entry=float(p.get("entry",0) or 0);qty=int(p.get("quantity",0) or 0);pnl=((float(ltp)-entry)*qty if side=="BUY" else (entry-float(ltp))*qty) if ltp else 0;rows.append({"Strategy":normalize_strategy(p.get("strategy","")),"Stock":symbol,"Side":side,"Entry":entry,"LTP":ltp,"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":qty,"Risk":p.get("actual_risk",p.get("risk")),"P&L":round(pnl,2),"Entry Time":p.get("entry_time")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:st.info("No open paper trades — waiting for complete alignment and an exact OHLC/PDH/PDL setup.")

st.markdown("<div class='sec'>📈 Live / Historical Charts</div>",unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:
    perf=[]
    for s in STRATEGIES:
        d=trades[trades["strategy"]==s];wins=int((d["pnl"]>0).sum());losses=int((d["pnl"]<0).sum());gross_win=float(d.loc[d["pnl"]>0,"pnl"].sum());gross_loss=abs(float(d.loc[d["pnl"]<0,"pnl"].sum()));total=len(d);pf=(gross_win/gross_loss) if gross_loss else (float("inf") if gross_win else 0);perf.append({"Strategy":s,"Trades":total,"Wins":wins,"Losses":losses,"Win Rate":(wins/total*100 if total else 0),"Net P&L":float(d["pnl"].sum()),"Profit Factor":pf})
    pdf=pd.DataFrame(perf);a,b=st.columns(2)
    with a:st.plotly_chart(px.bar(pdf,x="Strategy",y="Net P&L",title="Net P&L",text_auto=True),use_container_width=True)
    with b:st.plotly_chart(px.bar(pdf,x="Strategy",y="Win Rate",title="Win Rate %",text_auto=".1f"),use_container_width=True)
    a,b=st.columns(2)
    with a:st.plotly_chart(px.bar(pdf,x="Strategy",y="Profit Factor",title="Profit Factor",text_auto=".2f"),use_container_width=True)
    with b:
        wl=pdf[["Strategy","Wins","Losses"]].melt(id_vars="Strategy",var_name="Outcome",value_name="Trades");st.plotly_chart(px.bar(wl,x="Strategy",y="Trades",color="Outcome",barmode="stack",title="Wins vs Losses"),use_container_width=True)
    if "entry_time" in trades.columns:
        seq=trades.copy();seq["entry_time"]=pd.to_datetime(seq["entry_time"],errors="coerce");seq=seq.dropna(subset=["entry_time"]).sort_values("entry_time");seq["Cumulative P&L"]=seq.groupby("strategy")["pnl"].cumsum()
        if not seq.empty:st.plotly_chart(px.line(seq,x="entry_time",y="Cumulative P&L",color="strategy",markers=True,title="Cumulative P&L"),use_container_width=True)
    outcome=pd.Series({"Wins":int((trades["pnl"]>0).sum()),"Losses":int((trades["pnl"]<0).sum()),"Break-even":int((trades["pnl"]==0).sum())});st.plotly_chart(px.pie(values=outcome.values,names=outcome.index,title="Overall Win / Loss"),use_container_width=True)
else:st.info("Charts will populate from real paper-trade history. No artificial performance numbers are shown.")

st.markdown("<div class='sec'>🏆 Overall Strategy Performance — S1 to S5</div>",unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:st.dataframe(pdf,use_container_width=True,hide_index=True)
else:st.info("No historical paper trades yet. Overall statistics will appear after actual paper trades are recorded.")

st.markdown("<div class='sec'>📒 Master Strategy Journal — S1 to S5</div>",unsafe_allow_html=True)
try:
    from journal.master_journal import build_journal
    path=build_journal();jdf=pd.read_csv(path);st.dataframe(jdf.tail(25),use_container_width=True,hide_index=True);st.download_button("⬇️ Download Master Strategy Journal CSV",path.read_bytes(),"strategy_journal_master.csv","text/csv")
except Exception as e:st.warning(f"Journal unavailable: {type(e).__name__}")
quote=QUOTES[now.date().toordinal()%len(QUOTES)];st.markdown(f"<div class='quote'>🧠 Daily Trading Quote — “{quote}”</div>",unsafe_allow_html=True)
st.markdown("<div class='sec'>⚙️ System / Data Status</div>",unsafe_allow_html=True);st.json({"mode":"PAPER_ONLY","refresh_seconds":REFRESH,"capital_per_trade":CAPITAL,"max_trades_per_strategy_day":MAX_TRADES,"daily_loss_limit_per_strategy":DAILY_LOSS,"risk_range":"₹1,400–₹1,500","target_rr":RR,"nifty500_change":nifty,"sector_change":sector,"sector_mapping":sector_map,"sector_priced":sector_priced,"ad_ratio":ad,"ad_coverage":coverage,"market_data_coverage":priced,"buy_alignment":buy,"sell_alignment":sell,"open_positions":len(open_positions)})
st.caption("NSE Catalyst • one combined dashboard • S1–S5 • paper trading only • Dhan live data can be connected later.")
