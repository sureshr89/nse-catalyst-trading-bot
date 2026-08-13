from pathlib import Path
import streamlit as st
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}.block-container{padding:.4rem!important}[data-testid="stPageLink"] a{min-height:38px!important;margin-bottom:7px!important;border:1px solid #2b3b57!important;border-radius:10px!important;background:#142036!important;color:#e9f0f8!important;justify-content:center!important;font-size:.60rem!important;font-weight:700!important;width:100%!important}
.download-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.download-grid>*{width:100%!important}
</style>""",unsafe_allow_html=True)
with st.container(key="nav"):
 l,r=st.columns(2,gap="small")
 with l:st.page_link("app.py",label="🟢 BOT STATUS",width="stretch");st.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
 with r:st.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch");st.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")
def get(name):
 p=ROOT/"outputs"/name
 return p.read_bytes() if p.exists() else None
def button(name,label,mime):
 data=get(name)
 if data is not None:st.download_button(label,data=data,file_name=name,mime=mime,width="stretch")
 else:st.caption(f"{name} not available yet")
st.title("⬇️ Downloads")
st.caption("Trading records, scanner data and sector classification.")
st.subheader("Trading Data")
button("trades.csv","⬇️ ACTUAL / CAPITAL-MISSED TRADES CSV","text/csv")
button("signals.csv","⬇️ SCANNER SIGNALS CSV","text/csv")
button("bot_status.json","⬇️ BOT STATUS JSON","application/json")
button("paper_engine_state.json","⬇️ PAPER ENGINE STATE JSON","application/json")
st.subheader("🏭 Sector-wise Stock Classification")
p=ROOT/"data"/"nifty100_sectors.csv"
try:m=pd.read_csv(p)
except Exception:m=pd.DataFrame()
if not m.empty:
 st.write(f"{len(m)} stocks classified across {m['Sector'].nunique()} sectors.")
 summary=m.groupby("Sector").agg(Stocks=("Symbol","count")).reset_index().sort_values("Stocks",ascending=False)
 st.dataframe(summary,width="stretch",hide_index=True)
 st.download_button("⬇️ DOWNLOAD SECTOR-WISE STOCK LIST CSV",m.to_csv(index=False).encode(),"sector_wise_stock_list.csv","text/csv",width="stretch")
 st.download_button("⬇️ DOWNLOAD SECTOR SUMMARY CSV",summary.to_csv(index=False).encode(),"sector_summary.csv","text/csv",width="stretch")
 st.dataframe(m,width="stretch",hide_index=True)
else:st.info("The NIFTY 100 sector mapping will appear after the sector store prepares today's mapping.")
