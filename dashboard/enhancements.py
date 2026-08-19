"""Clean, mobile-first NSE Catalyst dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata")

def _csv(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()

def _sector_frame(q,u):
 if q is None or q.empty or u is None or u.empty or "Symbol" not in u.columns:return pd.DataFrame()
 cols=[c for c in ["Symbol","Sector","Industry"] if c in u.columns];m=u[cols].copy()
 if "Sector" not in m.columns:m["Sector"]=m.get("Industry","Unknown")
 m["Symbol"]=m["Symbol"].astype(str).str.upper().str.replace(".NS","",regex=False)
 x=q.copy();x["Symbol"]=x["Symbol"].astype(str).str.upper().str.replace(".NS","",regex=False)
 if "change_pct" not in x.columns:
  if {"LTP","PreviousClose"}.issubset(x.columns):x["change_pct"]=(pd.to_numeric(x.LTP,errors="coerce")-pd.to_numeric(x.PreviousClose,errors="coerce"))/pd.to_numeric(x.PreviousClose,errors="coerce")*100
  else:return pd.DataFrame()
 x["change_pct"]=pd.to_numeric(x["change_pct"],errors="coerce")
 x=m.merge(x[["Symbol","change_pct"]],on="Symbol",how="inner").dropna(subset=["change_pct"])
 if x.empty:return pd.DataFrame()
 return x.groupby("Sector").agg(Stocks=("Symbol","count"),ChangePct=("change_pct","mean"),Advances=("change_pct",lambda z:int((z>0).sum())),Declines=("change_pct",lambda z:int((z<0).sum()))).reset_index().sort_values("ChangePct",ascending=False)

def _master_journal(q,live,now):
 if len(q)<500:return
 p=OUTPUTS/"master_journal_cumulative.csv";row={"Date":str(now.date()),"NIFTY500ChangePct":live.get("nifty500_change_pct"),"ADRatio":live.get("ad_ratio"),"Advances":live.get("advances"),"Declines":live.get("declines"),"Unchanged":live.get("unchanged"),"PositiveSectors":live.get("positive_sectors"),"NegativeSectors":live.get("negative_sectors"),"SectorAlignmentPct":live.get("sector_alignment_pct"),"Coverage":len(q),"DataSource":"Dhan"}
 try:
  old=pd.read_csv(p) if p.exists() else pd.DataFrame();old=old[old["Date"].astype(str)!=str(now.date())] if not old.empty and "Date" in old else old;pd.concat([old,pd.DataFrame([row])],ignore_index=True).to_csv(p,index=False)
 except Exception:pass

def render_enhancements():
 now=datetime.now(IST)
 st.markdown("""<style>
 .block-container{padding-top:.7rem;padding-left:.7rem;padding-right:.7rem;max-width:1200px}
 @media(max-width:700px){.block-container{padding:.45rem}.stMetric{min-height:76px}.stDataFrame{font-size:12px}}
 .clock{background:linear-gradient(135deg,#07111f,#173a5e);color:white;border-radius:14px;padding:12px;text-align:center;margin-bottom:10px}
 .clock .t{font-size:25px;font-weight:900}.clock .s{font-size:11px;opacity:.82}
 .bias{border:1px solid #d7dde7;border-radius:14px;padding:10px;margin-bottom:12px;background:rgba(255,255,255,.04)}
 </style>""",unsafe_allow_html=True)
 st.markdown(f"<div class='clock'><div>🕒 LIVE APP TIME • INDIA</div><div class='t'>{now.strftime('%d %b %Y • %H:%M:%S')} IST</div><div class='s'>Dhan snapshot is tracked separately</div></div>",unsafe_allow_html=True)
 try:
  from market.nifty500_breadth import BREADTH
  from data.stock_universe import StockUniverse
  live=BREADTH.snapshot(force=False);u=StockUniverse().get_dataframe(refresh=False)
 except Exception as e:
  live={"quote_rows":pd.DataFrame(),"reason":str(e)};u=pd.DataFrame()
 q=live.get("quote_rows",pd.DataFrame());q=q if isinstance(q,pd.DataFrame) else pd.DataFrame(q);sec=_sector_frame(q,u);cov=len(q);ad=live.get("ad_ratio");chg=live.get("nifty500_change_pct")
 bull=(chg is not None and float(chg)>0 and ad is not None and float(ad)>1 and live.get("sector_alignment_pct",0)>0 and cov>=500)
 bear=(chg is not None and float(chg)<0 and ad is not None and float(ad)<1 and live.get("sector_alignment_pct",0)<0 and cov>=500)
 bias="🟢 BULLISH" if bull else "🔴 BEARISH" if bear else "⚪ WAIT / NO TRADE"
 st.markdown(f"<div class='bias'><b>🎯 MASTER MARKET BIAS</b><br><b>{bias}</b><br>NIFTY 500: {('+'+format(float(chg),'.2f')+'%') if chg is not None and float(chg)>=0 else (format(float(chg),'.2f')+'%' if chg is not None else '—')} &nbsp; • &nbsp; SECTOR: {live.get('sector_alignment_pct','—')} &nbsp; • &nbsp; A/D: {f'{float(ad):.2f}' if ad is not None and pd.notna(ad) else 'WAITING'}<br><small>🟢 Dhan update: {live.get('last_quote_time','—')} IST &nbsp; • &nbsp; Coverage: {cov}/500</small></div>",unsafe_allow_html=True)
 st.markdown("## ⚖️ S1–S5 STRATEGY COMPARISON")
 try:
  from dashboard.strategy_lab import render_strategy_lab
  render_strategy_lab()
 except Exception as e:st.error(f"Strategy comparison unavailable: {e}")
 st.markdown("---")
 tabs=st.tabs(["🟢 LIVE ANALYSIS","📚 PAST ANALYSIS","📖 STRATEGY THEORY"])
 with tabs[0]:
  st.subheader("Live analysis")
  a,b,c,d=st.columns(4);a.metric("NIFTY 500",f"{float(chg):+.2f}%" if chg is not None else "—");b.metric("A/D",f"{float(ad):.2f}" if ad is not None and pd.notna(ad) else "WAIT");c.metric("Adv / Dec",f"{live.get('advances',0)} / {live.get('declines',0)}");d.metric("Coverage",f"{cov}/500")
  if not sec.empty:
   st.markdown("### 🔥 Sector spikes")
   st.bar_chart(sec.set_index("Sector")["ChangePct"].head(8),height=240)
   with st.expander("Full sector numbers",expanded=False):st.dataframe(sec,width="stretch",hide_index=True)
  else:st.info("Sector analysis waits for verified stock prices + sector mapping.")
  with st.expander("500-stock detail",expanded=False):
   if not q.empty:st.dataframe(q,width="stretch",hide_index=True)
 with tabs[1]:
  st.subheader("Past completed session")
  try:
   from market.closed_session import load_saved
   pq,past=load_saved()
  except Exception as e:pq=pd.DataFrame();past={"coverage":"0/500","reason":str(e)}
  if not pq.empty:
   ps=_sector_frame(pq,u);a,b,c=st.columns(3);a.metric("Coverage",f"{len(pq)}/500");b.metric("A/D",past.get("ad_ratio","—"));c.metric("Session",past.get("session_date","—"))
   if not ps.empty:
    st.markdown("### 🔥 Past sector spikes");st.bar_chart(ps.set_index("Sector")["ChangePct"].head(8),height=240)
    with st.expander("Full past sector numbers",expanded=False):st.dataframe(ps,width="stretch",hide_index=True)
   with st.expander("500-stock past detail",expanded=False):st.dataframe(pq,width="stretch",hide_index=True)
  else:st.info(f"Past session not verified • coverage {past.get('coverage','0/500')}")
 with tabs[2]:
  st.subheader("S1–S5 theory")
  for sid,name in {"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}.items():
   with st.expander(f"{sid} • {name}",expanded=False):st.write("Entry → confirmation → SL → 1.25R target → exit or 15:00 IST square-off. NIFTY 500 + sector + A/D alignment is required; 500/500 breadth is required for a valid master signal.")
 if cov>=500:_master_journal(q,live,now)
 st.markdown("## 📥 DOWNLOADS")
 cumulative=_csv("master_journal_cumulative.csv")
 if not cumulative.empty:st.download_button("⬇️ Master CSV — Daily Cumulative",cumulative.to_csv(index=False).encode(),"master_journal_daily_cumulative.csv","text/csv",use_container_width=True)
 with st.expander("Other downloads",expanded=False):
  if not q.empty:st.download_button("Download current 500-stock snapshot",q.to_csv(index=False).encode(),f"nifty500_{now.date()}.csv","text/csv",use_container_width=True)
 st.markdown("## 💡 DAILY TRADING TIP")
 tips=["Protect capital first; opportunities return.","A planned trade is better than an emotional trade.","Wait for confirmation; missing one trade is cheaper than forcing one.","Risk small enough to stay in the game.","Let price confirm the idea before committing capital."]
 st.info(f"**{tips[now.date().toordinal()%len(tips)]}**")
