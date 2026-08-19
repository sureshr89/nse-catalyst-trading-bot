"""Master dashboard enhancements: compact analysis-first layout."""
from pathlib import Path
import os
from io import StringIO
import pandas as pd
import requests
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];OUTPUTS=ROOT/"outputs";MASTER_URL="https://images.dhan.co/api-data/api-scrip-master.csv";IST=ZoneInfo("Asia/Kolkata")
STRATEGIES={"S1":{"name":"PDH/PDL Sweep + Open Reclaim","entry":"BUY: Open > PDH → sweep below PDH → reclaim Open. SELL: Open < PDL → sweep above PDL → reject below Open.","sl":"BUY = sweep/session Low; SELL = sweep/session High.","target":"1.25R","time":"09:45–14:00 IST; square-off 15:00 IST.","sector":"NIFTY 500 direction + sector alignment + A/D >1 for BUY; opposite for SELL."},"S2":{"name":"PDH/PDL Breakout + Retest","entry":"Break PDH/PDL → retest → confirmation in breakout direction.","sl":"Beyond the retest swing.","target":"1.25R","time":"09:45–14:00 IST; square-off 15:00 IST.","sector":"NIFTY 500 + sector + A/D alignment required."},"S3":{"name":"PDL/PDH Sweep + Open Reclaim","entry":"Sweep PDL/PDH → reclaim/reject Open → confirmation.","sl":"Beyond sweep extreme.","target":"1.25R","time":"09:45–14:00 IST; square-off 15:00 IST.","sector":"Master breadth and sector alignment required."},"S4":{"name":"Intraday High/Low Breakout","entry":"Break a previously formed intraday High/Low with confirmation.","sl":"Opposite reference swing.","target":"1.25R","time":"09:45–14:00 IST; square-off 15:00 IST.","sector":"Master breadth, sector and A/D alignment required."},"S5":{"name":"Direct PDH/PDL Breakout","entry":"LTP breaks PDH or PDL with previous-candle confirmation.","sl":"PDH/PDL reference level.","target":"1.25R","time":"09:45–14:00 IST; square-off 15:00 IST.","sector":"500/500 breadth and sector alignment required."}}
def _secret(name):
 v=os.getenv(name,"")
 if v:return str(v).strip()
 try:return str(st.secrets.get(name,"")).strip()
 except Exception:return ""
def _test_10_stocks():
 cid=_secret("DHAN_CLIENT_ID");token=_secret("DHAN_ACCESS_TOKEN")
 if not cid or not token:return pd.DataFrame(),"DHAN credentials missing"
 h={"Accept":"application/json","Content-Type":"application/json","access-token":token,"client-id":cid};wanted=["TCS","RELIANCE","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","BHARTIARTL","LT","AXISBANK"]
 try:
  r=requests.get(MASTER_URL,timeout=15);r.raise_for_status();m=pd.read_csv(StringIO(r.text),low_memory=False);cols={str(c).strip().upper():c for c in m.columns};sc=next((cols[k] for k in ["SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME"] if k in cols),None);sid=next((cols[k] for k in ["SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"] if k in cols),None)
  if not sc or not sid:return pd.DataFrame(),"Dhan master symbol/security ID not recognised"
  x=m.copy();x["_sym"]=x[sc].astype(str).str.upper().str.strip();x=x[x["_sym"].isin(wanted)].drop_duplicates("_sym")
  if len(x)<10:return pd.DataFrame(),f"Mapped only {len(x)}/10 test stocks"
  ids=[int(float(v)) for v in x[sid]];q=requests.post("https://api.dhan.co/v2/marketfeed/ohlc",headers=h,json={"NSE_EQ":ids},timeout=15);b=q.json() if q.content else {}
  if q.status_code!=200:return pd.DataFrame(),f"Dhan HTTP {q.status_code}: {b.get('errorMessage') or b.get('message') or q.text[:200]}"
  data=b.get("data",{}).get("NSE_EQ",{});rows=[]
  for _,r0 in x.iterrows():
   k=str(int(float(r0[sid])));item=data.get(k,{}) or {};o=item.get("ohlc") or {};rows.append({"Symbol":r0["_sym"],"SecurityId":k,"LTP":item.get("last_price"),"Open":o.get("open"),"High":o.get("high"),"Low":o.get("low"),"Close":o.get("close")})
  df=pd.DataFrame(rows);return df,f"SUCCESS — Dhan returned {df['Close'].notna().sum()}/10 closes"
 except Exception as e:return pd.DataFrame(),f"{type(e).__name__}: {e}"
def _sector_frame(quotes,universe):
 if quotes is None or quotes.empty or universe is None or universe.empty:return pd.DataFrame()
 u=universe[[c for c in ["Symbol","Sector","Industry"] if c in universe.columns]].copy()
 if "Sector" not in u.columns:u["Sector"]=u.get("Industry","UNKNOWN")
 u["Symbol"]=u.Symbol.astype(str).str.upper().str.replace(".NS","",regex=False);q=quotes.copy();q["Symbol"]=q.Symbol.astype(str).str.upper().str.replace(".NS","",regex=False);q["change_pct"]=pd.to_numeric(q.get("change_pct"),errors="coerce")
 m=u.merge(q[["Symbol","change_pct"]],on="Symbol",how="inner").dropna(subset=["change_pct"])
 if m.empty:return pd.DataFrame()
 return m.groupby("Sector").agg(Stocks=("Symbol","count"),AverageChange=("change_pct","mean"),Advances=("change_pct",lambda x:int((x>0).sum())),Declines=("change_pct",lambda x:int((x<0).sum()))).reset_index().sort_values("AverageChange",ascending=False).reset_index(drop=True)
def _render_compact_sector(df,title):
 if df.empty:st.warning("Sector analysis waiting for verified stock + sector mapping.");return
 d=df.copy();d["AverageChange"]=pd.to_numeric(d["AverageChange"],errors="coerce");d["Bias"]=d["AverageChange"].map(lambda x:"🟢" if x>0 else "🔴" if x<0 else "⚪")
 with st.expander(title,expanded=True):
  st.caption(f"{len(d)} sectors • sorted strongest to weakest")
  st.dataframe(d[["Bias","Sector","Stocks","AverageChange","Advances","Declines"]],width="stretch",hide_index=True,column_config={"AverageChange":st.column_config.NumberColumn("Change %",format="%+.2f")})
def render_enhancements():
 now=datetime.now(IST)
 st.markdown(f"<div style='background:linear-gradient(90deg,#07111f,#16324f);color:white;border-radius:12px;padding:12px 16px;text-align:center;margin:4px 0 12px'><div style='font-size:12px;font-weight:800;letter-spacing:1px'>🕒 LIVE APP TIME • INDIA</div><div style='font-size:26px;font-weight:900'>{now.strftime('%d %b %Y • %H:%M:%S')} IST</div><div style='font-size:11px;opacity:.8'>Dhan data status is shown below • prices/analysis refresh independently</div></div>",unsafe_allow_html=True)
 try:
  from market.nifty500_breadth import BREADTH
  from data.stock_universe import StockUniverse
  live=BREADTH.snapshot(force=False);universe=StockUniverse().get_dataframe(refresh=False)
 except Exception as e:live={"complete":False,"sector_complete":False,"quote_rows":pd.DataFrame(),"reason":str(e)};universe=pd.DataFrame()
 q=live.get("quote_rows",pd.DataFrame());q=q if isinstance(q,pd.DataFrame) else pd.DataFrame(q);sec=_sector_frame(q,universe)
 n=live.get("nifty500_change_pct");ad=live.get("ad_ratio");coverage=len(q);sector_coverage=int(sec.Stocks.sum()) if not sec.empty else 0
 # Analysis is the main event: one compact overview, then three clearly separated analysis modes.
 st.markdown("### 🎯 Master Signal — What is the market saying now?")
 c1,c2,c3,c4=st.columns(4);c1.metric("NIFTY 500",f"{float(n):+.2f}%" if n is not None else "—");c2.metric("A/D Ratio",f"{float(ad):.2f}" if ad is not None and pd.notna(ad) else "WAITING");c3.metric("Breadth",f"{coverage}/500");c4.metric("Sector Map",f"{sector_coverage}/500")
 st.caption(f"🟢 RUNNING • Dhan • {now.strftime('%H:%M:%S')} IST • last verified data: {live.get('last_quote_time','—')} • no full-screen auto-refresh")
 tabs=st.tabs(["🟢 LIVE ANALYSIS","📚 PAST ANALYSIS","🧠 STRATEGY ANALYSIS"])
 with tabs[0]:
  st.subheader("Live Market Structure")
  a,b,c=st.columns(3);a.metric("Advances",live.get("advances",0));b.metric("Declines",live.get("declines",0));c.metric("Positive Sectors",live.get("positive_sectors",0))
  _render_compact_sector(sec,"📊 Sector Heatmap / Strength — Live")
  if not sec.empty:
   top=sec.head(8)[["Sector","AverageChange"]].copy();st.bar_chart(top.set_index("Sector"),height=260)
  with st.expander("🔍 Stock breadth details",expanded=False):
   if not q.empty:
    cols=[c for c in ["Symbol","LTP","PreviousClose","NetChange","change_pct","Volume"] if c in q.columns];st.dataframe(q[cols].head(30),width="stretch",hide_index=True)
 with tabs[1]:
  st.subheader("Past Session — verified only")
  try:
   from market.closed_session import load_saved
   past_df,past=load_saved()
  except Exception as e:past_df=pd.DataFrame();past={"coverage":"0/500","reason":str(e)}
  if not past_df.empty:
   pq=past_df.copy();pq["Symbol"]=pq.Symbol.astype(str).str.upper();
   if "change_pct" not in pq.columns and {"Close","PreviousClose"}.issubset(pq.columns):pq["change_pct"]=(pq.Close-pq.PreviousClose)/pq.PreviousClose*100
   ps=_sector_frame(pq,universe);pcols=[c for c in ["Symbol","Close","PreviousClose","change_pct"] if c in pq.columns]
   pc1,pc2,pc3=st.columns(3);pc1.metric("Coverage",f"{len(pq)}/500");pc2.metric("A/D",past.get("ad_ratio","—"));pc3.metric("Session",past.get("session_date","—"));_render_compact_sector(ps,"📊 Sector Heatmap / Strength — Past")
   with st.expander("🔍 Past stock details",expanded=False):st.dataframe(pq[pcols],width="stretch",hide_index=True)
  else:st.info(f"Past session not verified yet • coverage {past.get('coverage','0/500')}")
 with tabs[2]:
  st.subheader("S1–S5 — Strategy Analysis & Rules")
  st.caption("Permanent strategy reference. Expand only the strategy you want to study; this is not a daily trade list.")
  for s,r in STRATEGIES.items():
   with st.expander(f"{s} • {r['name']}",expanded=False):
    x,y=st.columns(2);x.markdown(f"**ENTRY**\n\n{r['entry']}");y.markdown(f"**SL**\n\n{r['sl']}\n\n**TARGET**\n\n{r['target']}");st.markdown(f"**TIME**  {r['time']}  
**SECTOR / BREADTH GATE**  {r['sector']}")
    st.info("Paper trading only • wait for all required confirmations • no partial 500-stock breadth")
 with st.expander("📚 Daily Journal / P&L",expanded=False):
  trades=_csv("trades.csv");signals=_csv("signals.csv");st.write(f"Taken trades: **{len(trades)}** • Eligible opportunities: **{len(signals)}**")
  if not trades.empty:st.dataframe(trades.tail(20),width="stretch",hide_index=True)
 with st.expander("🧰 Dhan diagnostics",expanded=False):
  if st.button("🔎 TEST DHAN — 10 STOCKS",type="primary",key="dhan10"):
   with st.spinner("Testing Dhan…"):df,msg=_test_10_stocks()
   st.session_state["dhan10_msg"]=msg;st.session_state["dhan10_df"]=df
  if "dhan10_msg" in st.session_state:
   st.success(st.session_state["dhan10_msg"]) if not st.session_state["dhan10_df"].empty else st.error(st.session_state["dhan10_msg"])
 with st.expander("📥 Downloads",expanded=False):
  if not q.empty:st.download_button("Download verified Dhan dataset",q.to_csv(index=False).encode(),f"nifty500_{now.date()}.csv","text/csv")
  journal=q.copy();
  if not journal.empty:journal["A/D Ratio"]=ad;journal["Advances"]=live.get("advances");journal["Declines"]=live.get("declines");st.download_button("Download Master Journal",journal.to_csv(index=False).encode(),f"master_journal_{now.date()}.csv","text/csv")
 st.markdown("<div class='sec'>💡 Daily Trading Tip</div>",unsafe_allow_html=True)
 tips=["Protect capital first; opportunities return.","A planned trade is better than an emotional trade.","Wait for confirmation; missing one trade is cheaper than forcing one.","Risk small enough to stay in the game.","Let price confirm the idea before committing capital."]
 st.markdown(f"<div style='border:1px solid #294367;border-radius:12px;padding:14px 18px;background:#101b2b;color:#f5f7fb;font-size:18px;font-weight:750'>“{tips[now.date().toordinal()%len(tips)]}”<div style='font-size:11px;color:#9fb1ca;margin-top:6px'>NSE Catalyst • Paper Trading</div></div>",unsafe_allow_html=True)
