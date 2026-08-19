"""Master dashboard enhancements: sector analysis, permanent S1-S5 rules, diagnostics and final downloads."""
from pathlib import Path
import os
from io import StringIO
import pandas as pd
import requests
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];OUTPUTS=ROOT/"outputs";MASTER_URL="https://images.dhan.co/api-data/api-scrip-master.csv";IST=ZoneInfo("Asia/Kolkata")
STRATEGIES={
"S1":{"name":"PDH/PDL Sweep + Open Reclaim","entry":"BUY: Open > PDH, sweep below PDH, reclaim Open. SELL: Open < PDL, sweep above PDL, reject back below Open.","sl":"BUY = current session Low; SELL = current session High.","target":"1.25R","time":"09:45–14:00 IST entries; force square-off 15:00 IST.","sector":"BUY: NIFTY 500 >0%, sector alignment >0%, A/D >1, coverage 500/500. SELL is the exact opposite.","notes":"Previous completed candle must agree with side. One paper trade per strategy/day."},
"S2":{"name":"PDH/PDL Breakout + Retest","entry":"BUY: break PDH → retest PDH → reclaim. SELL: break PDL → retest PDL → fail below.","sl":"BUY = retest Low; SELL = retest High.","target":"1.25R","time":"09:45–14:00 IST entries; force square-off 15:00 IST.","sector":"Same mandatory NIFTY 500 + sector + A/D gate with 500/500 verification.","notes":"No chase without retest; previous candle must agree."},
"S3":{"name":"PDL/PDH Sweep + Open Reclaim","entry":"BUY: Open > PDL, sweep below PDL, reclaim Open. SELL: Open < PDH, sweep above PDH, reject below Open.","sl":"BUY = current session Low; SELL = current session High.","target":"1.25R","time":"09:45–14:00 IST entries; force square-off 15:00 IST.","sector":"Same mandatory master alignment gate; partial breadth never qualifies.","notes":"Previous completed candle confirmation is mandatory."},
"S4":{"name":"Intraday High/Low Breakout","entry":"BUY = break previously formed intraday High. SELL = break previously formed intraday Low.","sl":"BUY = previous intraday Low; SELL = previous intraday High.","target":"1.25R","time":"09:45–14:00 IST entries; force square-off 15:00 IST.","sector":"Master NIFTY 500, sector and A/D alignment must be valid before eligibility.","notes":"Do not use the current unformed candle extreme as the reference."},
"S5":{"name":"Direct PDH/PDL Breakout","entry":"BUY = LTP breaks PDH. SELL = LTP breaks PDL.","sl":"BUY = PDH; SELL = PDL.","target":"1.25R","time":"09:45–14:00 IST entries; force square-off 15:00 IST.","sector":"Same mandatory master alignment gate and 500/500 breadth verification.","notes":"Previous completed candle must agree; paper trading only."}}

def _secret(name):
 v=os.getenv(name,"")
 if v:return str(v).strip()
 try:return str(st.secrets.get(name,"")).strip()
 except Exception:return ""
def _csv(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()
def _test_10_stocks():
 cid=_secret("DHAN_CLIENT_ID");token=_secret("DHAN_ACCESS_TOKEN")
 if not cid or not token:return pd.DataFrame(),"DHAN credentials missing"
 h={"Accept":"application/json","Content-Type":"application/json","access-token":token,"client-id":cid};wanted=["TCS","RELIANCE","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","BHARTIARTL","LT","AXISBANK"]
 try:
  r=requests.get(MASTER_URL,timeout=15);r.raise_for_status();m=pd.read_csv(StringIO(r.text),low_memory=False);cols={str(c).strip().upper():c for c in m.columns};sc=next((cols[k] for k in ["SEM_TRADING_SYMBOL","SM_SYMBOL_NAME","SYMBOL_NAME"] if k in cols),None);sid=next((cols[k] for k in ["SEM_SMST_SECURITY_ID","SEM_SECURITY_ID","SECURITY_ID"] if k in cols),None)
  if not sc or not sid:return pd.DataFrame(),f"Dhan master columns found: {list(m.columns)[:12]} — symbol/security ID not recognised"
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
 u=universe[[c for c in ["Symbol","Sector","Industry"] if c in universe.columns]].copy();
 if "Sector" not in u.columns:u["Sector"]=u.get("Industry","UNKNOWN")
 u["Symbol"]=u.Symbol.astype(str).str.upper().str.replace(".NS","",regex=False);q=quotes.copy();q["Symbol"]=q.Symbol.astype(str).str.upper().str.replace(".NS","",regex=False);q["change_pct"]=pd.to_numeric(q.get("change_pct"),errors="coerce")
 m=u.merge(q[["Symbol","change_pct"]],on="Symbol",how="inner").dropna(subset=["change_pct"])
 if m.empty:return pd.DataFrame()
 out=m.groupby("Sector").agg(Stocks=("Symbol","count"),AverageChange=("change_pct","mean"),Advances=("change_pct",lambda x:int((x>0).sum())),Declines=("change_pct",lambda x:int((x<0).sum()))).reset_index();out["Bias"]=out.AverageChange.map(lambda x:"POSITIVE" if x>0 else "NEGATIVE" if x<0 else "FLAT");return out.sort_values("AverageChange",ascending=False).reset_index(drop=True)
def _dhan_profile():
 cid=_secret("DHAN_CLIENT_ID");token=_secret("DHAN_ACCESS_TOKEN")
 if not cid or not token:return "NOT CONFIGURED","Credentials missing"
 try:
  r=requests.get("https://api.dhan.co/v2/profile",headers={"Accept":"application/json","access-token":token,"client-id":cid},timeout=10);b=r.json() if r.content else {}
  return ("PROFILE OK",f"Token {b.get('tokenValidity','—')} • Data plan {b.get('dataPlan','—')}") if r.status_code==200 else ("ERROR",f"{b.get('errorCode') or r.status_code}: {b.get('errorMessage') or b.get('message') or r.text[:160]}")
 except Exception as e:return "REQUEST ERROR",f"{type(e).__name__}: {e}"

def render_enhancements():
 now=datetime.now(IST)
 try:
  from market.nifty500_breadth import BREADTH
  from data.stock_universe import StockUniverse
  live=BREADTH.snapshot(force=False);universe=StockUniverse().get_dataframe(refresh=False)
 except Exception as e:live={"complete":False,"quote_rows":pd.DataFrame(),"reason":str(e)};universe=pd.DataFrame()
 lq=live.get("quote_rows",pd.DataFrame());lq=lq if isinstance(lq,pd.DataFrame) else pd.DataFrame(lq)
 live_sec=_sector_frame(lq,universe)
 st.markdown("<div class='sec'>🟢 LIVE / 📚 PAST — Sector Analysis</div>",unsafe_allow_html=True)
 lt,pt=st.tabs(["🟢 LIVE SECTOR ANALYSIS","📚 PAST SECTOR ANALYSIS"])
 with lt:
  st.caption(f"Live sector coverage: {len(lq)}/500 • A/D: {live.get('ad_ratio') if live.get('ad_ratio') is not None else 'WAITING'} • Sector alignment: {live.get('sector_alignment_pct') if live.get('sector_alignment_pct') is not None else 'WAITING'}")
  if live_sec.empty:st.warning("Sector analysis is locked until verified stock prices and a 500-stock sector map are available.")
  else:st.dataframe(live_sec,width="stretch",hide_index=True)
 with pt:
  try:
   from market.closed_session import load_saved
   past_df,past=load_saved()
  except Exception as e:past_df=pd.DataFrame();past={"complete":False,"reason":str(e),"coverage":"0/500"}
  if not past_df.empty:
   pq=past_df.copy();pq["Symbol"]=pq.Symbol.astype(str).str.upper();
   if "change_pct" not in pq.columns and {"Close","PreviousClose"}.issubset(pq.columns):pq["change_pct"]=(pq.Close-pq.PreviousClose)/pq.PreviousClose*100
   ps=_sector_frame(pq,universe);st.caption(f"Past session: {past.get('session_date','—')} • coverage {len(pq)}/500 • A/D {past.get('ad_ratio','—')}")
   if ps.empty:st.warning("Past sector mapping is not verified yet.")
   else:st.dataframe(ps,width="stretch",hide_index=True)
  else:
   st.warning(f"Past 500-stock session not stored yet • coverage {past.get('coverage','0/500')}")
   st.caption("No artificial A/D or sector values are shown. Use the closed-session verification in the data engine when the market is closed.")

 st.markdown("<div class='sec'>⚖️ S1–S5 Strategy Library — permanent rules</div>",unsafe_allow_html=True)
 st.caption("Collapse/expand each strategy. These are strategy definitions, not a daily trade list.")
 for s,r in STRATEGIES.items():
  with st.expander(f"{s} • {r['name']}",expanded=False):
   st.write(f"**ENTRY:** {r['entry']}");st.write(f"**EXIT / TARGET:** {r['target']} • exit immediately at SL or target • force square-off 15:00 IST.");st.write(f"**STOP LOSS:** {r['sl']}");st.write(f"**TIME:** {r['time']}");st.write(f"**SECTOR ANALYSIS:** {r['sector']}");st.write(f"**NOTES:** {r['notes']}");st.write("**Risk model:** ₹1,400–₹1,500 actual risk per trade • capital allocation up to ₹2,50,000 • RR 1:1.25.")
 st.subheader("Strategy Timing / Risk Summary")
 st.dataframe(pd.DataFrame([{"Strategy":s,"Entry":"09:45–14:00","Square-off":"15:00","RR":"1:1.25","Risk":"₹1,400–₹1,500","Sector gate":"MANDATORY","Breadth":"500/500"} for s in STRATEGIES]),width="stretch",hide_index=True)

 st.markdown("<div class='sec'>🧰 Dhan Data Diagnostics</div>",unsafe_allow_html=True);st.caption("Manual diagnostics only; no automatic screen refresh.")
 if st.button("🔎 TEST DHAN — 10 STOCKS",type="primary",key="dhan10"):
  with st.spinner("Requesting 10 NSE stocks from Dhan…"):df,msg=_test_10_stocks()
  st.session_state["dhan10_msg"]=msg;st.session_state["dhan10_df"]=df
 if "dhan10_msg" in st.session_state:
  msg=st.session_state["dhan10_msg"];df=st.session_state["dhan10_df"];st.success(msg) if not df.empty else st.error(msg)
  if not df.empty:st.dataframe(df,width="stretch",hide_index=True)
 if st.button("Test Dhan Authentication",key="dhan_auth"):
  s,d=_dhan_profile();st.session_state["dhan_auth_result"]={"status":s,"detail":d}
 if "dhan_auth_result" in st.session_state:
  a=st.session_state["dhan_auth_result"];st.write(f"**Dhan authentication:** {a['status']} — {a['detail']}")

 st.markdown("<div class='sec'>⬇️ Downloads — last section</div>",unsafe_allow_html=True)
 q=lq.copy()
 if not q.empty:st.download_button("⬇️ Download NIFTY 500 Dhan Quotes CSV",q.to_csv(index=False).encode(),f"nifty500_dhan_quotes_{now.date()}.csv","text/csv",use_container_width=True)
 master=_csv("strategy_journal_master.csv")
 if master.empty:master=_csv("master_journal.csv")
 if not master.empty:st.download_button("⬇️ Download Master Journal CSV",master.to_csv(index=False).encode(),f"nse_catalyst_master_journal_{now.date()}.csv","text/csv",use_container_width=True)
 for name,label in [("trades.csv","Actual Trades"),("signals.csv","All Signals")]:
  p=OUTPUTS/name
  if p.exists():st.download_button(f"⬇️ Download {label} CSV",p.read_bytes(),name,"text/csv",use_container_width=True)
 st.markdown("<div class='sec'>💡 Daily Trading Quote</div>",unsafe_allow_html=True)
 qs=["Protect your capital first; opportunities come again.","A good trade is planned before it is entered.","Discipline turns a strategy into an edge.","Wait for confirmation; forcing a trade is optional.","Trade the setup, not the emotion.","Consistency matters more than one big win.","Risk small enough to stay in the game.","Patience is a trading skill, not inactivity.","Your stop-loss is part of the strategy, not a failure.","Let price confirm your idea before you commit capital."]
 st.info(f"“{qs[now.date().toordinal()%len(qs)]}”")
 st.caption("NSE Catalyst • paper trading only • no automatic screen refresh")
