"""Additional master-dashboard panels without blocking network calls on page load."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import pandas as pd
import requests
import streamlit as st

ROOT=Path(__file__).resolve().parents[1];OUTPUTS=ROOT/"outputs";IST=ZoneInfo("Asia/Kolkata");MASTER_URL="https://images.dhan.co/api-data/api-scrip-master.csv"
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
def _csv(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()
def _num(v):
 try:return float(v)
 except Exception:return None
def _money(v):
 n=_num(v);return f"₹{n:,.2f}" if n is not None else "—"
def _find(df,names):
 if df.empty:return None
 lower={str(c).lower():c for c in df.columns}
 return next((lower[n.lower()] for n in names if n.lower() in lower),None)
def _dhan_diagnostic():
 def secret(name):
  value=os.getenv(name,"")
  if value:return str(value).strip()
  try:return str(st.secrets.get(name,"")).strip()
  except Exception:return ""
 client_id=secret("DHAN_CLIENT_ID");token=secret("DHAN_ACCESS_TOKEN")
 if not client_id or not token:return {"status":"NOT CONFIGURED","detail":"DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN missing"}
 headers={"Accept":"application/json","access-token":token,"client-id":client_id}
 try:
  profile=requests.get("https://api.dhan.co/v2/profile",headers=headers,timeout=10)
  try:body=profile.json()
  except Exception:body={}
  if profile.status_code!=200:return {"status":"ERROR","detail":f"{body.get('errorCode',profile.status_code)}: {body.get('errorMessage') or body.get('message') or profile.text[:180]}"}
  return {"status":"PROFILE OK","detail":f"Token: {body.get('tokenValidity','—')} • Data plan: {body.get('dataPlan','—')} • Data validity: {body.get('dataValidity','—')}"}
 except Exception as exc:return {"status":"REQUEST ERROR","detail":f"{type(exc).__name__}: {exc}"}

def render_enhancements():
 now=datetime.now(IST)
 st.markdown("<div class='sec'>🧰 Data, Quotes & Strategy Research</div>",unsafe_allow_html=True)
 if st.button("🔍 Test Dhan Connection",key="test_dhan_connection"):
  diag=_dhan_diagnostic();st.session_state["dhan_diag"]=diag
 else:diag=st.session_state.get("dhan_diag",{"status":"NOT TESTED","detail":"Press Test Dhan Connection"})
 st.markdown(f"<div class='status'><b>📡 Dhan diagnostic: {diag['status']}</b> • {diag['detail']}</div>",unsafe_allow_html=True)
 st.markdown("<div class='sec'>📥 Dhan Master Instrument CSV</div>",unsafe_allow_html=True)
 st.caption("Dhan master download is manual so opening the dashboard never waits for Dhan/NSE network requests.")
 if st.button("⬇️ Prepare Dhan Master CSV",key="prepare_dhan_master"):
  try:
   r=requests.get(MASTER_URL,timeout=30);r.raise_for_status();st.download_button("Download Dhan Master CSV",r.content,"dhan_scrip_master.csv","text/csv",key="dhan_master_csv")
  except Exception as exc:st.error(f"Dhan master CSV could not be downloaded: {type(exc).__name__}: {exc}")
 trades=_csv("trades.csv");signals=_csv("signals.csv")
 if not trades.empty and "strategy" in trades.columns:trades["strategy"]=trades["strategy"].astype(str).str.upper().str.strip().map(lambda x:x if x in STRATEGIES else ("S"+x.split("_")[-1] if x.startswith("STRATEGY_") else x))
 if not signals.empty and "strategy" in signals.columns:signals["strategy"]=signals["strategy"].astype(str).str.upper().str.strip()
 st.markdown("<div class='sec'>⚖️ S1–S5 Strategy Comparison</div>",unsafe_allow_html=True)
 rows=[]
 for s,name in STRATEGIES.items():
  t=trades[trades["strategy"].eq(s)].copy() if not trades.empty and "strategy" in trades.columns else pd.DataFrame();pc=_find(t,["pnl","P&L","profit_loss"]);p=pd.to_numeric(t[pc],errors="coerce").dropna() if pc else pd.Series(dtype=float);rows.append({"Strategy":s,"Name":name,"Taken":len(t),"Wins":int((p>0).sum()),"Losses":int((p<0).sum()),"Win %":round((p>0).mean()*100,1) if len(p) else None,"P&L":p.sum() if len(p) else 0})
 st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
 if not trades.empty:st.download_button("⬇️ Download Master Trades CSV",trades.to_csv(index=False).encode(),"master_trades.csv","text/csv",key="master_trades_csv")
 if not signals.empty:st.download_button("⬇️ Download Opportunities CSV",signals.to_csv(index=False).encode(),"eligible_opportunities.csv","text/csv",key="eligible_opportunities_csv")
