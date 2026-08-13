"""Streamlit page entrypoint for the read-only trading analysis."""
from pathlib import Path
import runpy
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[2]

st.set_page_config(page_title="NSE Catalyst | Analysis",page_icon="📊",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.65rem .65rem 2rem!important}
.nav-grid [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.55rem!important}
.nav-grid [data-testid="stColumn"]{width:calc(50% - .28rem)!important;flex:0 0 calc(50% - .28rem)!important;min-width:0!important}
.nav-grid [data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.4rem .2rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.64rem!important;font-weight:700!important;text-decoration:none!important;width:100%!important;box-sizing:border-box!important}
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
@media(max-width:768px){[data-testid="stMetric"]{min-height:54px!important;padding:.3rem .38rem!important}[data-testid="stMetricValue"]{font-size:.84rem!important}[data-testid="stMetricLabel"]{font-size:.55rem!important}}
</style>
""",unsafe_allow_html=True)

with st.container(key="nav_grid"):
    n1,n2=st.columns(2,gap="small"); n3,n4=st.columns(2,gap="small")
    n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢",width="stretch")
    n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌",width="stretch")
    n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊",width="stretch")
    n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️",width="stretch")

runpy.run_path(str(ROOT/"dashboard"/"analysis.py"),run_name="__main__")

# Sector results use the sector already stored on each actual closed trade first.
try:
    trades=pd.read_csv(ROOT/"outputs"/"trades.csv")
except Exception:
    trades=pd.DataFrame()

if not trades.empty and "status" in trades.columns:
    actual=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    actual=pd.DataFrame()

if not actual.empty:
    actual["pnl"]=pd.to_numeric(actual.get("pnl",0),errors="coerce").fillna(0)
    if "sector" in actual.columns:
        actual["Sector"]=actual["sector"].fillna("UNKNOWN").astype(str).str.strip().replace("","UNKNOWN")
    else:
        actual["Sector"]="UNKNOWN"
    rows=[]
    for sector,g in actual.groupby("Sector",dropna=False):
        wins=int((g["pnl"]>0).sum()); losses=int((g["pnl"]<0).sum())
        rows.append({"Sector":str(sector),"Trades":len(g),"Wins":wins,"Losses":losses,"Win Rate %":round(wins/len(g)*100,1) if len(g) else 0.0,"P&L":round(float(g["pnl"].sum()),2)})
    sector_stats=pd.DataFrame(rows).sort_values(["P&L","Win Rate %"],ascending=[False,False]).reset_index(drop=True)
    st.markdown("### 🏭 Sector Performance — Which Sector Favors the Strategy?")
    st.caption("Based directly on the sector stored in CLOSED actual trades. Capital-missed opportunities are excluded.")
    st.dataframe(sector_stats,width="stretch",hide_index=True)
    import plotly.express as px
    fig=px.bar(sector_stats,x="Sector",y="P&L",text="Trades",title="Actual P&L by Sector")
    fig.update_layout(height=360,margin=dict(l=10,r=10,t=55,b=90),yaxis_title="₹")
    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False,"staticPlot":True})
else:
    st.markdown("### 🏭 Sector Performance — Which Sector Favors the Strategy?")
    st.info("No closed actual trades yet. Sector results will populate automatically after an actual trade closes.")
