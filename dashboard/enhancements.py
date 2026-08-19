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
def render_enhancements():
 now=datetime.now(IST)
 st.markdown("""<style>
 .stApp{background:linear-gradient(180deg,#f4f7fb 0%,#eef3f9 100%)}.block-container{max-width:760px!important;padding:.45rem .55rem 1rem!important}.hero{background:linear-gradient(135deg,#071a35,#124e78,#087f8c);color:#fff;border-radius:18px;padding:15px;margin-bottom:10px;box-shadow:0 7px 22px #123b5526}.hero h1{color:#fff!important;font-size:1.32rem!important;margin:0!important}.hero small{color:#d9f4f6}.hero .time{font-size:1.1rem;font-weight:850;margin-top:5px}.box{background:#fff;border:1px solid #dce5ee;border-radius:15px;padding:11px;margin:7px 0;box-shadow:0 3px 12px #1f3b4d0c}.title{font-size:.68rem;font-weight:850;color:#667085;text-transform:uppercase}.big{font-size:1.1rem;font-weight:900}.green{color:#087f3e}.red{color:#c62828}.amber{color:#b26a00}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}.cell{background:#f3f7fa;border-radius:10px;padding:7px}.lab{font-size:.57rem;color:#667085}.val{font-size:.8rem;font-weight:850;color:#172033}.strat{border-left:4px solid #087f8c}.shead{display:flex;justify-content:space-between;gap:5px;font-size:.87rem;font-weight:900;color:#172033}.pill{font-size:.57rem;background:#e5f5f6;color:#087f8c;padding:4px 7px;border-radius:20px;white-space:nowrap}.summary{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.tip{background:#eaf7f7;border:1px solid #bce3e5;border-radius:14px;padding:11px;font-size:.76rem;color:#17343a}@media(max-width:480px){.block-container{padding:.3rem .4rem!important}.grid{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:1.14rem!important}}
 </style>""",unsafe_allow_html=True)
 st.markdown(f"<div class='hero'><h1>📊 NSE CATALYST</h1><small>Paper Trading • ₹2.5L / Strategy • 1 Trade / Strategy / Day</small><div class='time'>🕒 {now.strftime('%d %b %Y • %H:%M:%S')} IST</div><small>Dhan cycle • 15 seconds</small></div>",unsafe_allow_html=True)
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
 st.markdown("### ⚡ TODAY • S1–S5")
 names={"S1":"Sweep + Open Reclaim","S2":"Breakout + Retest","S3":"Reverse Sweep + Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
 for sid,name in names.items():st.markdown(f"<div class='box strat'><div class='shead'><span>{sid} • {name}</span><span class='pill'>1 TRADE ONLY</span></div><div class='grid'><div class='cell'><div class='lab'>STATUS</div><div class='val'>WAITING</div></div><div class='cell'><div class='lab'>SIGNAL TIME</div><div class='val'>—</div></div><div class='cell'><div class='lab'>ENTRY / EXIT</div><div class='val'>— / —</div></div><div class='cell'><div class='lab'>P&L</div><div class='val'>₹0</div></div></div></div>",unsafe_allow_html=True)
 st.markdown("### 💰 TODAY'S P&L");st.markdown("<div class='summary'><div class='box'><div class='big'>0 / 5</div><div class='title'>Trades Done</div></div><div class='box'><div class='big'>0</div><div class='title'>Wins</div></div><div class='box'><div class='big'>0</div><div class='title'>Losses</div></div><div class='box'><div class='big'>₹0</div><div class='title'>Total P&L</div></div></div>",unsafe_allow_html=True)
 st.markdown("### 📥 MASTER CUMULATIVE CSV");c=_csv("master_cumulative.csv")
 if not c.empty:st.download_button("⬇️ Download Master CSV",c.to_csv(index=False).encode(),"master_cumulative.csv","text/csv",use_container_width=True)
 else:st.caption("Daily trade records will be added here.")
 st.markdown("### 💡 DAILY TRADING TIP");tips=["Follow the rule, not the emotion.","One qualified trade per strategy. Then stop.","Do not chase a missed signal.","Risk stays near ₹1,400–₹1,500.","Let the system decide; execute the plan."];st.markdown(f"<div class='tip'>💡 {tips[now.date().toordinal()%len(tips)]}</div>",unsafe_allow_html=True)
 if now.hour>=16:_archive(q,now)
