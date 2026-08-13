from pathlib import Path
import runpy
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[2]
SIGNALS=ROOT/"outputs"/"signals.csv"
try:
    df=pd.read_csv(SIGNALS)
    if not df.empty:
        dates=pd.to_datetime(df.get("timestamp",pd.Series(index=df.index)),errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        for col in ["symbol","signal","setup_type"]:
            if col not in df.columns: df[col]=""
        key=dates+"|"+df["symbol"].astype(str).str.upper().str.strip()+"|"+df["signal"].astype(str).str.upper().str.strip()+"|"+df["setup_type"].astype(str).str.upper().str.strip()
        cleaned=df.loc[~key.duplicated(keep="first")].copy()
        if len(cleaned)!=len(df): cleaned.to_csv(SIGNALS,index=False)
except Exception: pass
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.4rem .2rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.68rem!important;font-weight:700!important;text-decoration:none!important}
@media(max-width:768px){[data-testid="stPageLink"] a{font-size:.60rem!important}}
</style>
""",unsafe_allow_html=True)
n1,n2=st.columns(2,gap="small"); n3,n4=st.columns(2,gap="small")
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️")
runpy.run_path(str(ROOT/"pages"/"current.py"),run_name="__main__")
