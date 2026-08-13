import streamlit as st
st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stHorizontalBlock"]{flex-direction:row!important;flex-wrap:nowrap!important}
[data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:38px!important;margin-bottom:7px!important;border:1px solid #2b3b57!important;border-radius:10px!important;background:#142036!important;color:#e9f0f8!important;font-size:.60rem!important;font-weight:700!important;width:100%!important}
</style>
""",unsafe_allow_html=True)
with st.container(key="main_nav"):
    left,right=st.columns(2,gap="small")
    with left:
        st.page_link("app.py",label="🟢 BOT STATUS",width="stretch")
        st.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
    with right:
        st.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch")
        st.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")

from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
def file_bytes(name):
    p=ROOT/"outputs"/name
    return p.read_bytes() if p.exists() else None

def download(name,label,mime):
    data=file_bytes(name)
    if data is not None: st.download_button(label,data=data,file_name=name,mime=mime,width="stretch")
    else: st.info(f"{name} is not available yet.")

st.title("⬇️ Downloads")
st.caption("Download the persistent trading records and research data.")
st.subheader("Trading Data")
for name,label in [("trades.csv","⬇️ Actual / Capital-Missed Trades CSV"),("signals.csv","⬇️ Scanner Signals CSV"),("bot_status.json","⬇️ Bot Status JSON"),("paper_engine_state.json","⬇️ Paper Engine State JSON")]:
    download(name,label,"text/csv" if name.endswith(".csv") else "application/json")

st.subheader("Sector-wise Stock Classification")
try:
    mapping=pd.read_csv(ROOT/"data"/"nifty100_sector_mapping.csv")
except Exception:
    mapping=pd.DataFrame()
if not mapping.empty:
    st.dataframe(mapping,width="stretch",hide_index=True)
    st.download_button("⬇️ SECTOR-WISE STOCK LIST CSV",mapping.to_csv(index=False).encode(),"sector_wise_stock_list.csv","text/csv",width="stretch")
else:
    st.info("Sector mapping file is not available yet.")
