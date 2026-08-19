"""Dashboard diagnostics. Network calls are manual so page load stays fast."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
import os
import pandas as pd
import requests
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata"); MASTER_URL="https://images.dhan.co/api-data/api-scrip-master.csv"
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}

def _secret(name):
    v=os.getenv(name,"")
    if v:return str(v).strip()
    try:return str(st.secrets.get(name,"")).strip()
    except Exception:return ""

def _csv(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def _find(df,names):
    if df.empty:return None
    lower={str(c).lower():c for c in df.columns};return next((lower[n.lower()] for n in names if n.lower() in lower),None)

def _test_10_stocks():
    cid=_secret("DHAN_CLIENT_ID"); token=_secret("DHAN_ACCESS_TOKEN")
    if not cid or not token:return pd.DataFrame(),"DHAN credentials missing"
    h={"Accept":"application/json","Content-Type":"application/json","access-token":token,"client-id":cid}
    wanted=["TCS","RELIANCE","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","BHARTIARTL","LT","AXISBANK"]
    try:
        r=requests.get(MASTER_URL,timeout=15);r.raise_for_status();m=pd.read_csv(StringIO(r.text),low_memory=False)
        cols={str(c).upper():c for c in m.columns};sc=cols.get("SEM_TRADING_SYMBOL");sid=cols.get("SEM_SECURITY_ID");ex=cols.get("SEM_EXM_EXCH_ID");seg=cols.get("SEM_SEGMENT")
        if not sc or not sid:return pd.DataFrame(),"Dhan master missing trading-symbol/security-id columns"
        x=m.copy();x["_sym"]=x[sc].astype(str).str.upper().str.strip()
        if ex:x=x[x[ex].astype(str).str.upper().eq("NSE")]
        if seg:x=x[x[seg].astype(str).str.upper().eq("E")]
        x=x[x["_sym"].isin(wanted)].drop_duplicates("_sym")
        if len(x)<10:return pd.DataFrame(),f"Mapped only {len(x)}/10 test stocks"
        ids=[int(float(v)) for v in x[sid]]
        q=requests.post("https://api.dhan.co/v2/marketfeed/ohlc",headers=h,json={"NSE_EQ":ids},timeout=15)
        try:b=q.json()
        except Exception:b={}
        if q.status_code!=200:return pd.DataFrame(),f"Dhan HTTP {q.status_code}: {b.get('errorCode') or b.get('errorType') or ''} {b.get('errorMessage') or b.get('message') or q.text[:200]}"
        data=b.get("data",{}).get("NSE_EQ",{});rows=[]
        for _,r0 in x.iterrows():
            k=str(int(float(r0[sid])));item=data.get(k,{}) or {};o=item.get("ohlc") or {};rows.append({"Symbol":r0["_sym"],"SecurityId":k,"LTP":item.get("last_price"),"Open":o.get("open"),"High":o.get("high"),"Low":o.get("low"),"Close":o.get("close")})
        return pd.DataFrame(rows),f"SUCCESS — Dhan returned {sum(pd.notna(pd.DataFrame(rows)['Close']))}/10 closes"
    except Exception as e:return pd.DataFrame(),f"{type(e).__name__}: {e}"

def _dhan_profile():
    cid=_secret("DHAN_CLIENT_ID");token=_secret("DHAN_ACCESS_TOKEN")
    if not cid or not token:return "NOT CONFIGURED","Credentials missing"
    try:
        r=requests.get("https://api.dhan.co/v2/profile",headers={"Accept":"application/json","access-token":token,"client-id":cid},timeout=10);b=r.json() if r.content else {}
        if r.status_code!=200:return "ERROR",f"{b.get('errorCode') or r.status_code}: {b.get('errorMessage') or b.get('message') or r.text[:160]}"
        return "PROFILE OK",f"Token {b.get('tokenValidity','—')} • Data plan {b.get('dataPlan','—')}"
    except Exception as e:return "REQUEST ERROR",f"{type(e).__name__}: {e}"

def render_enhancements():
    st.markdown("<div class='sec'>🧰 Dhan Data Diagnostics</div>",unsafe_allow_html=True)
    st.caption("No Dhan/NSE network request is made automatically. This prevents the app from buffering on every load.")
    if st.button("🔎 TEST DHAN — 10 STOCKS",type="primary",key="dhan10"):
        with st.spinner("Requesting 10 NSE stocks from Dhan…"):
            df,msg=_test_10_stocks()
        st.session_state["dhan10_msg"]=msg;st.session_state["dhan10_df"]=df
    if "dhan10_msg" in st.session_state:
        msg=st.session_state["dhan10_msg"];st.success(msg) if not st.session_state["dhan10_df"].empty else st.error(msg)
        if not st.session_state["dhan10_df"].empty:st.dataframe(st.session_state["dhan10_df"],width="stretch",hide_index=True)
    if st.button("Test Dhan Authentication",key="dhan_auth"):
        s,d=_dhan_profile();st.session_state["dhan_auth"]=(s,d)
    if "dhan_auth" in st.session_state:
        s,d=st.session_state["dhan_auth"];st.markdown(f"**Dhan authentication:** {s} — {d}")
    st.markdown("<div class='sec'>⚖️ S1–S5 Strategy Comparison</div>",unsafe_allow_html=True)
    trades=_csv("trades.csv");rows=[]
    for s,name in STRATEGIES.items():
        t=trades[trades["strategy"].astype(str).str.upper().eq(s)] if not trades.empty and "strategy" in trades.columns else pd.DataFrame();pc=_find(t,["pnl","P&L","profit_loss"]);p=pd.to_numeric(t[pc],errors="coerce").dropna() if pc else pd.Series(dtype=float);rows.append({"Strategy":s,"Name":name,"Taken":len(t),"Wins":int((p>0).sum()),"Losses":int((p<0).sum()),"Win %":round((p>0).mean()*100,1) if len(p) else None,"P&L":p.sum() if len(p) else 0})
    st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
