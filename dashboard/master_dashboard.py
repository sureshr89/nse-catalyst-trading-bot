"""Single combined NSE Catalyst dashboard for S1-S5 paper trading."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import sys
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
IST=ZoneInfo("Asia/Kolkata")
REFRESH=15
CAPITAL=250000
MIN_RISK=1400
MAX_RISK=1500
RR=1.25
MAX_TRADES=1
DAILY_LOSS=1500
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
QUOTES=["Process first. Profit follows disciplined execution.","Protect capital, wait for alignment, then act.","A good trade is a rule-following trade, not just a winning trade.","Consistency comes from repeating a tested process.","No setup is also a valid decision.","Risk is fixed before the entry; everything else follows."]

st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=REFRESH*1000,key="master_refresh")
st.markdown("""
<style>
:root{--panel:#111b2b;--panel2:#0f1928;--border:#2b4163;--muted:#9fb1ca;--text:#f4f7fb;--blue:#62a8ff;--green:#43d17a;--red:#ff6675;--gold:#ffd166}
html,body,[class*="css"]{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.block-container{max-width:1450px;padding-top:1.4rem;padding-bottom:2.5rem}
.title{font-size:clamp(2rem,4vw,3rem);font-weight:900;line-height:1.08;letter-spacing:-.025em;margin:4px 0 8px;color:var(--text)}
.sub{color:var(--muted);font-size:.92rem;line-height:1.5;margin-bottom:20px}
.sec{font-size:clamp(1.18rem,2.5vw,1.5rem);font-weight:850;margin:27px 0 12px;line-height:1.2;color:var(--text)}
.metric-grid,.rule-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}
.card{border:1px solid var(--border);background:linear-gradient(145deg,var(--panel),var(--panel2));border-radius:14px;padding:13px 12px;min-height:92px;display:flex;flex-direction:column;justify-content:center;overflow:hidden;box-sizing:border-box;box-shadow:0 5px 18px rgba(0,0,0,.12)}
.card small{display:block;color:var(--muted);font-size:.67rem;line-height:1.2;font-weight:800;text-transform:uppercase;letter-spacing:.045em;white-space:normal}
.card b{font-size:clamp(1.03rem,2vw,1.35rem);line-height:1.2;display:block;margin-top:7px;color:var(--text);overflow-wrap:anywhere}
.strategy-grid{display:flex;flex-wrap:nowrap;gap:12px;overflow-x:auto;overflow-y:hidden;padding:2px 2px 10px;scrollbar-width:thin;-webkit-overflow-scrolling:touch}
.strategy{flex:0 0 calc((100% - 48px)/5);min-width:210px;border:1px solid var(--border);background:linear-gradient(145deg,var(--panel),var(--panel2));border-radius:15px;padding:17px;min-height:155px;box-sizing:border-box;box-shadow:0 5px 18px rgba(0,0,0,.12)}
.strategy h4{font-size:1.08rem;margin:0 0 10px;line-height:1.25;color:var(--text)}
.strategy .muted{font-size:.92rem}
.muted{color:var(--muted);line-height:1.5}
.quote{border-left:4px solid var(--blue);background:var(--panel);padding:13px 16px;border-radius:9px;font-style:italic;color:#dbe6f5}
.data-state{border:1px solid var(--border);background:linear-gradient(145deg,var(--panel),var(--panel2));border-radius:14px;padding:14px 16px;margin-top:12px;color:var(--text);line-height:1.55}
.data-state .ok{color:var(--green);font-weight:850}.data-state .wait{color:var(--gold);font-weight:850}.data-state .bad{color:var(--red);font-weight:850}
.gate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}.gate{border:1px solid var(--border);border-radius:12px;padding:12px;background:var(--panel2)}.gate b{display:block;font-size:.95rem}.gate span{display:block;color:var(--muted);font-size:.82rem;margin-top:4px}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.rule-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.strategy{flex-basis:270px}}
@media(max-width:700px){.block-container{padding:1rem .85rem 2rem}.title{font-size:1.75rem}.sub{font-size:.82rem;margin-bottom:16px}.sec{font-size:1.15rem;margin-top:22px;margin-bottom:10px}.metric-grid,.rule-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.strategy-grid{gap:9px;padding-bottom:9px}.strategy{flex-basis:255px;min-height:125px;padding:14px}.card{min-height:82px;padding:11px 10px;border-radius:12px}.card small{font-size:.62rem}.card b{font-size:1rem;margin-top:6px}.strategy h4{font-size:1rem}.strategy .muted{font-size:.86rem}.gate-grid{grid-template-columns:1fr;gap:8px}}
@media(max-width:380px){.metric-grid,.rule-grid{grid-template-columns:1fr}.title{font-size:1.6rem}.card b{font-size:1.02rem}}
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

now=datetime.now(IST)
diag=load_json("scanner_diagnostics.json")
state=load_json("paper_engine_state.json")
bot_status=load_json("bot_status.json")
trades=load_csv("trades.csv")
if not trades.empty:
    if "strategy" not in trades.columns:trades["strategy"]=""
    trades["strategy"]=trades["strategy"].map(normalize_strategy)
    if "pnl" in trades:trades["pnl"]=pd.to_numeric(trades["pnl"],errors="coerce").fillna(0)

nifty=diag.get("nifty500_change_pct")
sector=diag.get("sector_change_pct")
ad=diag.get("ad_ratio")
coverage=str(diag.get("ad_coverage","0/500"))
priced=str(diag.get("market_data_coverage","0/500"))
sector_map=str(diag.get("sector_mapping","0/500"))
sector_priced=str(diag.get("sector_priced","0/500"))
full_breadth=coverage=="500/500"
sector_ok=bool(diag.get("sector_available")) and sector_map=="500/500" and sector_priced=="500/500"
buy=bool(diag.get("buy_alignment"))
sell=bool(diag.get("sell_alignment"))
bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

st.markdown("<div class='title'>📊 NSE Catalyst — Master Dashboard</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 combined • PAPER TRADING ONLY • auto-refresh {REFRESH}s • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)
st.markdown("<div class='sec'>🎯 Master Market Alignment</div>",unsafe_allow_html=True)
master_cards=[k("NIFTY 500",pct(nifty)),k("SECTORS",pct(sector)),k("A/D RATIO",f"{float(ad):.2f}" if full_breadth and ad is not None else "WAITING"),k("BREADTH",coverage),k("SECTOR DATA",sector_priced),k("MASTER BIAS",bias)]
st.markdown("<div class='metric-grid'>"+"".join(master_cards)+"</div>",unsafe_allow_html=True)

if full_breadth and sector_ok and (buy or sell):
    st.markdown("<div class='data-state'><span class='ok'>● LIVE ALIGNMENT READY</span> — All 500 stocks are priced, sector data is complete, and the master market gate is satisfied.</div>",unsafe_allow_html=True)
else:
    reasons=[]
    if not full_breadth:reasons.append(f"NIFTY 500 breadth {coverage}, requires 500/500")
    if not sector_ok:reasons.append(f"sector data mapping {sector_map}, priced {sector_priced}, requires 500/500")
    if nifty is None:reasons.append("NIFTY 500 live change waiting for market data")
    if ad is None:reasons.append("A/D waiting for complete 500-stock prices")
    st.markdown("<div class='data-state'><span class='wait'>● TRADING WAITING</span> — " + "; ".join(reasons) + ". No strategy is allowed to trade until the master gate is complete.</div>",unsafe_allow_html=True)

buy_gate="PASS ✓" if buy else "WAIT"
sell_gate="PASS ✓" if sell else "WAIT"
st.markdown(f"<div class='gate-grid'><div class='gate'><b>🟢 BUY GATE · {buy_gate}</b><span>NIFTY 500 &gt; 0% + Sector &gt; 0% + A/D &gt; 1 + 500/500</span></div><div class='gate'><b>🔴 SELL GATE · {sell_gate}</b><span>NIFTY 500 &lt; 0% + Sector &lt; 0% + A/D &lt; 1 + 500/500</span></div><div class='gate'><b>📡 DATA · {priced}</b><span>All live strategy scans use the same 15-second master snapshot.</span></div></div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🔒 Fixed Paper-Trading Rules</div>",unsafe_allow_html=True)
rules=[k("CAPITAL / TRADE",money(CAPITAL)),k("RISK / TRADE","₹1,400–₹1,500"),k("TARGET / TRADE","1.25R"),k("MAX TRADES / STRATEGY","1 / day"),k("DAILY LOSS / TRADE","₹1,500"),k("REFRESH","15 sec")]
st.markdown("<div class='rule-grid'>"+"".join(rules)+"</div>",unsafe_allow_html=True)
st.caption("Position size is derived from actual Entry→SL distance. If actual risk is outside ₹1,400–₹1,500, the trade is rejected. Maximum one paper trade per strategy per day. No real orders.")

st.markdown("<div class='sec'>🔥 All 5 Strategies — One-Glance Board</div>",unsafe_allow_html=True)
st.markdown("<div class='strategy-grid'>",unsafe_allow_html=True)
for s in STRATEGIES:
    td=trades[trades["strategy"]==s] if not trades.empty else pd.DataFrame()
    today_td=td
    if not td.empty and "entry_time" in td.columns:
        dt=pd.to_datetime(td["entry_time"],errors="coerce")
        today_td=td[dt.dt.date==now.date()]
    wins=int((today_td["pnl"]>0).sum()) if not today_td.empty and "pnl" in today_td else 0
    losses=int((today_td["pnl"]<0).sum()) if not today_td.empty and "pnl" in today_td else 0
    pnl=float(today_td["pnl"].sum()) if not today_td.empty and "pnl" in today_td else 0
    locked=len(today_td)>=MAX_TRADES or pnl<=-DAILY_LOSS
    status="🔒 LOCKED" if locked else "🟢 ALIGNED" if (buy or sell) else "⚪ WAITING"
    st.markdown(f"<div class='strategy'><h4>{s} • {status}</h4><div class='muted'>{STRATEGIES[s]}</div><br><span>Trades <b>{len(today_td)}/{MAX_TRADES}</b> • Wins <b>{wins}</b> • Losses <b>{losses}</b></span><br><br><span>Daily P&amp;L <b>{money(pnl)}</b></span></div>",unsafe_allow_html=True)
st.markdown("</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>💼 Current Paper Trades — All Strategies</div>",unsafe_allow_html=True)
open_positions=state.get("open_positions",{}) if isinstance(state,dict) else {}
if open_positions:
    rows=[]
    for symbol,p in open_positions.items():
        ltp=p.get("last_live_price",p.get("entry"));side=p.get("signal","—");entry=float(p.get("entry",0) or 0);qty=int(p.get("quantity",0) or 0);pnl=((float(ltp)-entry)*qty if side=="BUY" else (entry-float(ltp))*qty) if ltp else 0
        rows.append({"Strategy":normalize_strategy(p.get("strategy","")),"Stock":symbol,"Side":side,"Entry":entry,"LTP":ltp,"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":qty,"Risk":p.get("actual_risk",p.get("risk")),"P&L":round(pnl,2),"Entry Time":p.get("entry_time")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:st.info("No open paper trades — waiting for complete alignment and an exact OHLC/PDH/PDL setup.")

st.markdown("<div class='sec'>📈 Performance & Analysis</div>",unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:
    perf=[]
    for s in STRATEGIES:
        d=trades[trades["strategy"]==s];wins=int((d["pnl"]>0).sum());losses=int((d["pnl"]<0).sum());gross_win=float(d.loc[d["pnl"]>0,"pnl"].sum());gross_loss=abs(float(d.loc[d["pnl"]<0,"pnl"].sum()));total=len(d);pf=(gross_win/gross_loss) if gross_loss else (float("inf") if gross_win else 0);perf.append({"Strategy":s,"Trades":total,"Wins":wins,"Losses":losses,"Win Rate":(wins/total*100 if total else 0),"Net P&L":float(d["pnl"].sum()),"Profit Factor":pf})
    pdf=pd.DataFrame(perf)
    a,b=st.columns(2)
    with a:st.plotly_chart(px.bar(pdf,x="Strategy",y="Net P&L",title="💰 Net P&L",text_auto=True),use_container_width=True)
    with b:st.plotly_chart(px.bar(pdf,x="Strategy",y="Win Rate",title="🎯 Win Rate %",text_auto=".1f"),use_container_width=True)
    a,b=st.columns(2)
    with a:st.plotly_chart(px.bar(pdf,x="Strategy",y="Profit Factor",title="📊 Profit Factor",text_auto=".2f"),use_container_width=True)
    with b:
        wl=pdf[["Strategy","Wins","Losses"]].melt(id_vars="Strategy",var_name="Outcome",value_name="Trades");st.plotly_chart(px.bar(wl,x="Strategy",y="Trades",color="Outcome",barmode="stack",title="🔥 Wins vs Losses"),use_container_width=True)
    if "entry_time" in trades.columns:
        seq=trades.copy();seq["entry_time"]=pd.to_datetime(seq["entry_time"],errors="coerce");seq=seq.dropna(subset=["entry_time"]).sort_values("entry_time");seq["Cumulative P&L"]=seq.groupby("strategy")["pnl"].cumsum()
        if not seq.empty:st.plotly_chart(px.line(seq,x="entry_time",y="Cumulative P&L",color="strategy",markers=True,title="📈 Cumulative P&L"),use_container_width=True)
else:st.info("Charts will populate from real paper-trade history. No artificial performance numbers are shown.")

st.markdown("<div class='sec'>🏆 Strategy Comparison</div>",unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:st.dataframe(pdf,use_container_width=True,hide_index=True)
else:st.info("No historical paper trades yet. Strategy probabilities and rankings will appear after actual paper trades are recorded.")

st.markdown("<div class='sec'>📒 Master Strategy Journal — S1 to S5</div>",unsafe_allow_html=True)
try:
    from journal.master_journal import build_journal
    path=build_journal();jdf=pd.read_csv(path);st.dataframe(jdf.tail(25),use_container_width=True,hide_index=True);st.download_button("⬇️ Download Master Strategy Journal CSV",path.read_bytes(),"strategy_journal_master.csv","text/csv")
except Exception as e:
    journal_path=ROOT/"outputs"/"strategy_journal_master.csv"
    if journal_path.exists():
        jdf=pd.read_csv(journal_path);st.dataframe(jdf.tail(25),use_container_width=True,hide_index=True);st.download_button("⬇️ Download Master Strategy Journal CSV",journal_path.read_bytes(),"strategy_journal_master.csv","text/csv")
    else:st.info("Journal will appear automatically after the first paper-trading cycle.")

quote=QUOTES[now.date().toordinal()%len(QUOTES)];st.markdown(f"<div class='quote'>🧠 Daily Trading Quote — “{quote}”</div>",unsafe_allow_html=True)
st.markdown("<div class='sec'>⚙️ System / Data Status</div>",unsafe_allow_html=True)
worker_state=str(bot_status.get("status","UNKNOWN"));worker_message=str(bot_status.get("message","No worker status yet."));worker_error=bot_status.get("last_scan_error") or bot_status.get("error")
data_ready=full_breadth and sector_ok and nifty is not None and ad is not None
status_payload={"mode":"PAPER_ONLY","refresh_seconds":REFRESH,"capital_per_trade":CAPITAL,"max_trades_per_strategy_day":MAX_TRADES,"daily_loss_limit_per_trade":DAILY_LOSS,"risk_range":"₹1,400–₹1,500","target_rr":RR,"nifty500_change":nifty,"sector_change":sector,"sector_mapping":sector_map,"sector_priced":sector_priced,"ad_ratio":ad,"ad_coverage":coverage,"market_data_coverage":priced,"buy_alignment":buy,"sell_alignment":sell,"open_positions":len(open_positions),"data_ready":data_ready,"worker_status":worker_state}
st.json(status_payload)
if data_ready:
    st.success("Live master data is complete. S1–S5 can evaluate setups on the next 15-second cycle.")
else:
    st.warning("Live master data is not complete yet. This is a real-data safety block — no artificial NIFTY 500, sector, or A/D values are generated.")
if worker_error:st.error(f"Worker/scanner error: {worker_error}")
st.caption(f"Worker: {worker_state} • {worker_message} • NSE Catalyst • S1–S5 • paper trading only • Dhan live data can be connected later.")
