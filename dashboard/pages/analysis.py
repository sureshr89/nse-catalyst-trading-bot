from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
ROOT=Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Analysis",page_icon="📊",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}.block-container{padding:.4rem!important}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metric-card{background:#111b2d;border:1px solid #26344d;border-radius:10px;padding:8px}.metric-card small{display:block;color:#9fb0c7;font-size:.58rem}.metric-card b{color:#f4f7fb;font-size:.82rem}.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}[data-testid="stPageLink"] a{min-height:38px!important;margin-bottom:7px!important;border:1px solid #2b3b57!important;border-radius:10px!important;background:#142036!important;color:#e9f0f8!important;justify-content:center!important;font-size:.60rem!important;font-weight:700!important}
</style>""",unsafe_allow_html=True)
with st.container(key="nav"):
 l,r=st.columns(2,gap="small")
 with l:st.page_link("app.py",label="🟢 BOT STATUS",width="stretch");st.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
 with r:st.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch");st.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")
def grid(x):st.markdown('<div class="metric-grid">'+''.join(f'<div class="metric-card"><small>{a}</small><b>{b}</b></div>' for a,b in x)+'</div>',unsafe_allow_html=True)
try:t=pd.read_csv(ROOT/"outputs/trades.csv")
except:t=pd.DataFrame()
a=t[t["status"].astype(str).str.upper().eq("CLOSED")].copy() if not t.empty and "status" in t.columns else pd.DataFrame()
if not a.empty:a["pnl"]=pd.to_numeric(a.get("pnl",0),errors="coerce").fillna(0);a["Sector"]=a.get("sector",pd.Series("UNKNOWN",index=a.index)).fillna("UNKNOWN").astype(str).replace("","UNKNOWN")
w=int((a.pnl>0).sum()) if not a.empty else 0;l=int((a.pnl<0).sum()) if not a.empty else 0;p=float(a.pnl.sum()) if not a.empty else 0
st.title("📊 Strategy Analysis");st.caption("Actual CLOSED trades only. Capital-missed opportunities remain separate.")
grid([("Actual Trades",len(a)),("Win Rate",f"{w/len(a)*100:.1f}%" if len(a) else "0.0%"),("Actual P&L",f"₹{p:,.2f}"),("Capital-Missed",int(t.status.astype(str).str.upper().str.startswith("MISSED_CAPITAL").sum()) if not t.empty and "status" in t.columns else 0)])
st.subheader("🏭 Sector Performance — Which Sector Favors the Strategy?")
if a.empty:st.info("No closed actual trades yet.")
else:
 rows=[]
 for s,g in a.groupby("Sector"):
  ww=int((g.pnl>0).sum());ll=int((g.pnl<0).sum());rows.append({"Sector":s,"Trades":len(g),"Wins":ww,"Losses":ll,"Win Rate %":round(ww/len(g)*100,1),"P&L":round(float(g.pnl.sum()),2)})
 ss=pd.DataFrame(rows).sort_values("P&L",ascending=False);st.dataframe(ss,width="stretch",hide_index=True)
 for y,title in [("P&L","Actual P&L by Sector"),("Win Rate %","Win Rate by Sector")]:
  f=px.bar(ss,x="Sector",y=y,text="Trades",title=title);f.update_layout(height=300,margin=dict(l=5,r=5,t=45,b=80));st.plotly_chart(f,width="stretch",config={"staticPlot":True,"displayModeBar":False,"scrollZoom":False})
st.subheader("Stock-Level Performance")
if a.empty:st.info("No actual trades available.")
else:st.dataframe(a[[c for c in ["symbol","sector","signal","entry","exit_price","pnl"] if c in a.columns]].iloc[::-1],width="stretch",hide_index=True)
