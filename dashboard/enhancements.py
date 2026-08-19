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
    sq=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in q.columns),None); su=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in u.columns),None); sc=next((c for c in ["Sector","sector","Industry"] if c in u.columns),None)
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

def render_enhancements():
    now=datetime.now(IST)
    st.markdown("""<style>
    .block-container{max-width:760px!important;padding:.4rem .55rem 1rem!important}.hero{background:linear-gradient(135deg,#111827,#1d4ed8);color:#fff;border-radius:16px;padding:14px;margin-bottom:9px;box-shadow:0 5px 18px #0002}.hero h1{color:#fff!important;font-size:1.3rem!important;margin:0!important}.hero .time{font-size:1.08rem;font-weight:800;margin-top:4px}.hero small{color:#dbeafe}.box{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:10px;margin:7px 0;box-shadow:0 2px 9px #0000000a}.title{font-size:.68rem;font-weight:800;color:#667085;text-transform:uppercase}.big{font-size:1.08rem;font-weight:850}.green{color:#07883f}.red{color:#c52222}.amber{color:#b54708}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:7px}.cell{background:#f8fafc;border-radius:9px;padding:6px}.lab{font-size:.56rem;color:#667085}.val{font-size:.78rem;font-weight:800}.strat{border-left:4px solid #2563eb}.shead{display:flex;justify-content:space-between;font-size:.86rem;font-weight:850}.pill{font-size:.58rem;background:#eef2ff;padding:4px 7px;border-radius:20px}.summary{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.tip{background:#eff6ff;border:1px solid #bfdbfe;border-radius:13px;padding:10px;font-size:.74rem}@media(max-width:480px){.block-container{padding:.3rem .4rem!important}.grid{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:1.12rem!important}}
    </style>""",unsafe_allow_html=True)
    st.markdown(f"<div class='hero'><h1>📊 NSE CATALYST</h1><small>Paper Trading • ₹2.5L per Strategy • 1 Trade / Strategy / Day</small><div class='time'>🕒 {now.strftime('%d %b %Y • %H:%M:%S')} IST</div><small>Dhan cycle: 15 seconds</small></div>",unsafe_allow_html=True)
    try:
        from market.nifty500_breadth import BREADTH
        from data.stock_universe import StockUniverse
        live=BREADTH.snapshot(force=False);u=StockUniverse().get_dataframe(refresh=False)
    except Exception as e:live={"quote_rows":pd.DataFrame(),"reason":str(e)};u=pd.DataFrame()
    q=live.get("quote_rows",pd.DataFrame());q=q if isinstance(q,pd.DataFrame) else pd.DataFrame(q);chg=live.get("nifty500_change_pct");ad=live.get("ad_ratio");cov=len(q);sp=_sector_pct(q,u);sp=live.get("sector_alignment_pct") if live.get("sector_alignment_pct") is not None else sp
    buy=chg is not None and ad is not None and sp is not None and float(chg)>0 and float(ad)>1 and float(sp)>0 and cov>=500
    sell=chg is not None and ad is not None and sp is not None and float(chg)<0 and float(ad)<1 and float(sp)<0 and cov>=500
    state="🟢 BUY ALIGNED" if buy else "🔴 SELL ALIGNED" if sell else "⚪ WAIT — NO ENTRY";cl="green" if buy else "red" if sell else "amber"
    st.markdown(f"<div class='box'><div class='title'>Master Entry Gate</div><div class='big {cl}'>{state}</div><div class='grid'><div class='cell'><div class='lab'>NIFTY 500</div><div class='val'>{f'{float(chg):+.2f}%' if chg is not None else '—'}</div></div><div class='cell'><div class='lab'>A/D</div><div class='val'>{f'{float(ad):.2f}' if ad is not None else '—'}</div></div><div class='cell'><div class='lab'>SECTOR</div><div class='val'>{f'{float(sp):+.2f}%' if sp is not None else '—'}</div></div><div class='cell'><div class='lab'>COVERAGE</div><div class='val'>{cov}/500</div></div></div></div>",unsafe_allow_html=True)
    st.markdown("### ⚡ TODAY • S1–S5")
    names={"S1":"Sweep + Open Reclaim","S2":"Breakout + Retest","S3":"Reverse Sweep + Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
    for sid,name in names.items():
        st.markdown(f"<div class='box strat'><div class='shead'><span>{sid} • {name}</span><span class='pill'>1 TRADE ONLY</span></div><div class='grid'><div class='cell'><div class='lab'>STATUS</div><div class='val'>WAITING</div></div><div class='cell'><div class='lab'>SIGNAL TIME</div><div class='val'>—</div></div><div class='cell'><div class='lab'>ENTRY / EXIT</div><div class='val'>— / —</div></div><div class='cell'><div class='lab'>P&L</div><div class='val'>₹0</div></div></div></div>",unsafe_allow_html=True)
    st.markdown("### 💰 TODAY'S P&L")
    st.markdown("<div class='summary'><div class='box'><div class='big'>0 / 5</div><div class='title'>Trades Done</div></div><div class='box'><div class='big'>0</div><div class='title'>Wins</div></div><div class='box'><div class='big'>0</div><div class='title'>Losses</div></div><div class='box'><div class='big'>₹0</div><div class='title'>Total P&L</div></div></div>",unsafe_allow_html=True)
    st.markdown("### 📥 MASTER CUMULATIVE CSV")
    c=_csv("master_cumulative.csv")
    if not c.empty:st.download_button("⬇️ Download Master CSV",c.to_csv(index=False).encode(),"master_cumulative.csv","text/csv",use_container_width=True)
    else:st.caption("Daily trade records will be added here.")
    st.markdown("### 💡 DAILY TRADING TIP")
    tips=["Follow the rule, not the emotion.","One qualified trade per strategy. Then stop.","Do not chase a missed signal.","Risk stays near ₹1,400–₹1,500.","Let the system decide; execute the plan."]
    st.markdown(f"<div class='tip'>💡 {tips[now.date().toordinal()%len(tips)]}</div>",unsafe_allow_html=True)
    if now.hour>=16:_archive(q,now)
