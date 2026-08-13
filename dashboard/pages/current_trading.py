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
.nav-grid [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.55rem!important}
.nav-grid [data-testid="stColumn"]{width:calc(50% - .28rem)!important;flex:0 0 calc(50% - .28rem)!important;min-width:0!important}
.nav-grid [data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.4rem .2rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.66rem!important;font-weight:700!important;text-decoration:none!important;width:100%!important;box-sizing:border-box!important}
</style>
""",unsafe_allow_html=True)
with st.container(key="nav_grid"):
    n1,n2=st.columns(2,gap="small")
    n3,n4=st.columns(2,gap="small")
    n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢",width="stretch")
    n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌",width="stretch")
    n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊",width="stretch")
    n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️",width="stretch")
runpy.run_path(str(ROOT/"pages"/"current.py"),run_name="__main__")
