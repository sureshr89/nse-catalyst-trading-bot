"""NSE Catalyst - mobile execution dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata")

def _csv(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def _sector_pct(q,u):
    if q.empty or u.empty:return None
    sq=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in q.columns),None);su=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in u.columns),None);sc=next((c for c in ["Sector","sector","Industry"] if c in u.columns),None)
    if not sq or not su or not sc:return None
    m=u[[su,sc]].copy();m.columns=["Symbol","Sector"];x=q.copy();x["Symbol"]=x[sq].astype(str).str.upper().str.replace(".NS","",regex=False);m["Symbol"]=m["Symbol"].astype(str).str.upper().str.replace(".NS","",regex=False)
    if "change_pct" not in x.columns and {"LTP","PreviousClose"}.issubset(x.columns):
        pc=pd.to_numeric(x["PreviousClose"],errors="coerce");x["change_pct"]=(pd.to_numeric(x["LTP"],errors="coerce")-pc)/pc*100
    if "change_pct" not in x.columns:return None
    x=x.merge(m,on="Symbol",how="inner");return float(pd.to_numeric(x["change_pct"],errors="coerce").mean()) if not x.empty else None

def _archive(q,now):
    if now.hour<16 or len(q)<500:return
    OUTPUTS.mkdir(exist_ok=True);p=OUTPUTS/"master_cumulative.csv";day=str(now.date())
    try:
        x=q.copy();x.insert(0,"Date",day);x["ArchiveTimeIST"]=now.strftime("%Y-%m-%d %H:%M:%S");old=pd.read_csv(p) if p.exists() else pd.DataFrame()
        if not old.empty and "Date" in old:old=old[old.Date.astype(str)!=day]
        pd.concat([old,x],ignore_index=True).to_csv(p,index=False)
    except Exception:pass

def _quote_table(q):
    if q.empty:return pd.DataFrame()
    x=q.copy()
    symbol=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol","symbol"] if c in x.columns),None)
    ltp=next((c for c in ["LTP","ltp","LastPrice","LastTradedPrice"] if c in x.columns),None)
    prev=next((c for c in ["PreviousClose","previous_close","PrevClose","prev_close"] if c in x.columns),None)
    chg=next((c for c in ["change_pct","ChangePct","change_percent"] if c in x.columns),None)
    vol=next((c for c in ["Volume","volume","TotalTradedVolume"] if c in x.columns),None)
    cols=[]
    rename={}
    if symbol:cols.append(symbol);rename[symbol]="SYMBOL"
    if ltp:cols.append(ltp);rename[ltp]="LTP"
    if prev:cols.append(prev);rename[prev]="PREV CLOSE"
    if chg:cols.append(chg);rename[chg]="CHANGE %"
    if vol:cols.append(vol);rename[vol]="VOLUME"
    if not cols:return x
    out=x[cols].copy().rename(columns=rename)
    if "CHANGE %" not in out.columns and {"LTP","PREV CLOSE"}.issubset(out.columns):
        p=pd.to_numeric(out["PREV CLOSE"],errors="coerce");out["CHANGE %"]=(pd.to_numeric(out["LTP"],errors="coerce")-p)/p*100
    for c in ["LTP","PREV CLOSE","CHANGE %"]:
        if c in out.columns:out[c]=pd.to_numeric(out[c],errors="coerce").round(2)
    return out

def render_enhancements():
    now=datetime.now(IST)
    st.markdown("""<style>
    .stApp{background:#000!important}.block-container{max-width:760px!important;padding:.45rem .55rem 1rem!important}
    .hero{background:linear-gradient(135deg,#020406,#07151F,#062B32);color:#fff;border-radius:18px;padding:15px;margin-bottom:10px;border:1px solid #17313A}.hero h1{color:#fff!important;font-size:1.32rem!important;margin:0!important}.hero small{color:#d9f4f6}.hero .time{font-size:1.1rem;font-weight:850;margin-top:5px}
    .box{background:#0B0F14;border:1px solid #26313D;border-radius:15px;padding:11px;margin:7px 0}.title{font-size:.68rem;font-weight:850;color:#AAB6C3;text-transform:uppercase}.big{font-size:1.1rem;font-weight:900}.green{color:#20E38A}.red{color:#FF5C67}.amber{color:#FFD166}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}.cell{background:#111820;border:1px solid #202A34;border-radius:10px;padding:7px}.lab{font-size:.57rem;color:#AAB6C3}.val{font-size:.8rem;font-weight:850;color:#F5F7FB}.strat{border-left:4px solid #00D9FF}.shead{display:flex;justify-content:space-between;gap:5px;font-size:.87rem;font-weight:900;color:#F5F7FB}.pill{font-size:.57rem;background:#092C32;color:#5DE7F5;padding:4px 7px;border-radius:20px;white-space:nowrap}.summary{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.tip{background:#0B2023;border:1px solid #164B50;border-radius:14px;padding:11px;font-size:.76rem;color:#D8F7FA}
    .quote-head{color:#F5F7FB!important;font-weight:900;font-size:1.05rem;margin:14px 0 7px}.quote-note{color:#AAB6C3;font-size:.72rem;margin-bottom:7px}
    [data-testid="stDataFrame"]{border:1px solid #26313D;border-radius:12px;overflow:hidden}.stDownloadButton button{background:#08242A!important;color:#5DE7F5!important;border:1px solid #00D9FF!important;font-weight:800}
    @media(max-width:480px){.block-container{padding:.3rem .4rem!important}.grid{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:1.14rem!important}}
    </style>""",unsafe_allow_html=True)
    st.markdown(f"<div class='hero'><h1>📊 NSE CATALYST</h1><small>Paper Trading • ₹2.5L / Strategy • 1 Trade / Strategy / Day</small><div class='time'>🕒 {now.strftime('%d %b %Y • %H:%M:%S')} IST</div><small>Live refresh • 25 seconds</small></div>",unsafe_allow_html=True)
    try:
        from market.nifty500_breadth import BREADTH
        from data.stock_universe import StockUniverse
        live=BREADTH.snapshot(force=False);u=StockUniverse().get_dataframe(refresh=False)
    except Exception as e:live={"quote_rows":pd.DataFrame(),"reason":str(e)};u=pd.DataFrame()
    q=live.get("quote_rows",pd.DataFrame());q=q if isinstance(q,pd.DataFrame) else pd.DataFrame(q);chg=live.get("nifty500_change_pct");ad=live.get("ad_ratio");cov=len(q);sp=live.get("sector_alignment_pct")
    if sp is None:sp=_sector_pct(q,u)
    buy=chg is not None and ad is not None and sp is not None and float(chg)>0 and float(ad)>1 and float(sp)>0 and cov>=500;sell=chg is not None and ad is not None and sp is not None and float(chg)<0 and float(ad)<1 and float(sp)<0 and cov>=500
    state="🟢 BUY ALIGNED" if buy else "🔴 SELL ALIGNED" if sell else "⚪ WAIT — NO ENTRY";cl="green" if buy else "red" if sell else "amber"
    st.markdown(f"<div class='box'><div class='title'>Master Entry Gate</div><div class='big {cl}'>{state}</div><div class='grid'><div class='cell'><div class='lab'>NIFTY 500</div><div class='val'>{f'{float(chg):+.2f}%' if chg is not None else '—'}</div></div><div class='cell'><div class='lab'>A/D</div><div class='val'>{f'{float(ad):.2f}' if ad is not None else '—'}</div></div><div class='cell'><div class='lab'>SECTOR</div><div class='val'>{f'{float(sp):+.2f}%' if sp is not None else '—'}</div></div><div class='cell'><div class='lab'>COVERAGE</div><div class='val'>{cov}/500</div></div></div></div>",unsafe_allow_html=True)

    # Live quotes: visible table + downloadable CSV on every refresh.
    qt=_quote_table(q)
    st.markdown(f"<div class='quote-head'>📈 LIVE STOCK QUOTES ({len(qt)})</div><div class='quote-note'>Latest Dhan quote snapshot • refreshes every 25 seconds</div>",unsafe_allow_html=True)
    if not qt.empty:
        st.download_button("⬇️ Download Live Quotes CSV",qt.to_csv(index=False).encode("utf-8"),"live_quotes.csv","text/csv",use_container_width=True,key="live_quotes_csv")
        st.dataframe(qt,use_container_width=True,height=430,hide_index=True)
    else:
        st.warning("No live stock quotes received from Dhan yet. The next 25-second refresh will retry.")

    st.markdown("### ⚡ TODAY • S1–S5")
    names={"S1":"Sweep + Open Reclaim","S2":"Breakout + Retest","S3":"Reverse Sweep + Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
    for sid,name in names.items():st.markdown(f"<div class='box strat'><div class='shead'><span>{sid} • {name}</span><span class='pill'>1 TRADE ONLY</span></div><div class='grid'><div class='cell'><div class='lab'>STATUS</div><div class='val'>WAITING</div></div><div class='cell'><div class='lab'>SIGNAL TIME</div><div class='val'>—</div></div><div class='cell'><div class='lab'>ENTRY / EXIT</div><div class='val'>— / —</div></div><div class='cell'><div class='lab'>P&L</div><div class='val'>₹0</div></div></div></div>",unsafe_allow_html=True)
    st.markdown("### 💰 TODAY'S P&L");st.markdown("<div class='summary'><div class='box'><div class='big'>0 / 5</div><div class='title'>Trades Done</div></div><div class='box'><div class='big'>0</div><div class='title'>Wins</div></div><div class='box'><div class='big'>0</div><div class='title'>Losses</div></div><div class='box'><div class='big'>₹0</div><div class='title'>Total P&L</div></div></div>",unsafe_allow_html=True)
    st.markdown("### 📥 MASTER CUMULATIVE CSV");c=_csv("master_cumulative.csv")
    if not c.empty:st.download_button("⬇️ Download Master CSV",c.to_csv(index=False).encode("utf-8"),"master_cumulative.csv","text/csv",use_container_width=True,key="master_csv")
    else:st.caption("Cumulative file will be available after the daily archive is created. Use Live Quotes CSV above to download the current stock data now.")
    st.markdown("### 💡 DAILY TRADING TIP");tips=["Follow the rule, not the emotion.","One qualified trade per strategy. Then stop.","Do not chase a missed signal.","Risk stays near ₹1,400–₹1,500.","Let the system decide; execute the plan."];st.markdown(f"<div class='tip'>💡 {tips[now.date().toordinal()%len(tips)]}</div>",unsafe_allow_html=True)
    if now.hour>=16:_archive(q,now)
