"""Analysis page wrapper."""
from pathlib import Path
import runpy
import pandas as pd
import streamlit as st

PROJECT_ROOT=Path(__file__).resolve().parents[2]
ANALYSIS_FILE=PROJECT_ROOT/"dashboard"/"analysis.py"

st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.5rem .5rem 1.2rem!important}
[data-testid="stPageLink"] a{min-height:40px!important;padding:.35rem .15rem!important;font-size:.62rem!important}
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
[data-testid="stMetric"]{padding:.3rem .4rem!important;min-height:52px!important}
[data-testid="stMetricLabel"]{font-size:.56rem!important}
[data-testid="stMetricValue"]{font-size:.78rem!important}
@media(max-width:768px){div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:.35rem!important}}
</style>
""",unsafe_allow_html=True)

n1,n2=st.columns(2,gap="small"); n3,n4=st.columns(2,gap="small")
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️")

runpy.run_path(str(ANALYSIS_FILE),run_name="__main__")

# IMPORTANT: outputs is at repository root, not dashboard/outputs.
try:
    trades=pd.read_csv(PROJECT_ROOT/"outputs"/"trades.csv")
except Exception:
    trades=pd.DataFrame()

actual=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()

st.markdown('<div class="section-title">🏭 Sector Performance — Which Sector Favors the Strategy?</div>',unsafe_allow_html=True)
if actual.empty:
    st.info("No closed actual trades yet.")
else:
    actual["pnl"]=pd.to_numeric(actual.get("pnl",0),errors="coerce").fillna(0)
    actual["Sector"]=actual.get("sector",pd.Series("UNKNOWN",index=actual.index)).fillna("UNKNOWN").astype(str)
    rows=[]
    for sector,g in actual.groupby("Sector"):
        pnl=g["pnl"]; wins=int((pnl>0).sum()); losses=int((pnl<0).sum())
        rows.append({"Sector":sector,"Trades":len(g),"Wins":wins,"Losses":losses,"Win Rate %":round(wins/len(g)*100,1),"P&L":round(float(pnl.sum()),2),"Avg P&L":round(float(pnl.mean()),2)})
    sector_stats=pd.DataFrame(rows).sort_values("P&L",ascending=False).reset_index(drop=True)
    st.caption("CLOSED actual trades only. Capital-missed trades are excluded.")
    st.dataframe(sector_stats,use_container_width=True,hide_index=True)
    import plotly.express as px
    fig=px.bar(sector_stats,x="Sector",y="P&L",text="Trades",title="Actual P&L by Sector")
    st.plotly_chart(fig,use_container_width=True,config={"staticPlot":True,"displayModeBar":False})
    fig2=px.bar(sector_stats,x="Sector",y="Win Rate %",text="Trades",title="Strategy Win Rate by Sector")
    st.plotly_chart(fig2,use_container_width=True,config={"staticPlot":True,"displayModeBar":False})
