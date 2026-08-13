from pathlib import Path
import json
import streamlit as st
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.45rem .55rem 1.5rem!important}
.nav-grid [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.55rem!important}
.nav-grid [data-testid="stColumn"]{width:calc(50% - .28rem)!important;flex:0 0 calc(50% - .28rem)!important;min-width:0!important}
.nav-grid [data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.4rem .2rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.64rem!important;font-weight:700!important;text-decoration:none!important;width:100%!important;box-sizing:border-box!important}
.download-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.download-grid>*{width:100%!important}
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
@media(max-width:768px){.block-container{padding:.35rem .35rem 1rem!important}.nav-grid [data-testid="stHorizontalBlock"]{gap:.35rem!important}.nav-grid [data-testid="stPageLink"] a{min-height:40px!important;font-size:.60rem!important}}
</style>
""",unsafe_allow_html=True)

# Exactly four navigation buttons, always visible as 2 x 2.
with st.container(key="nav_grid"):
    a,b=st.columns(2,gap="small")
    a.page_link("app.py",label="🟢 BOT STATUS",width="stretch")
    b.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",width="stretch")
    c,d=st.columns(2,gap="small")
    c.page_link("pages/analysis.py",label="📊 ANALYSIS",width="stretch")
    d.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",width="stretch")

def existing_bytes(name):
    p=ROOT/"outputs"/name
    return p.read_bytes() if p.exists() else None

def csv_bytes(name,columns):
    data=existing_bytes(name)
    if data is not None:
        return data
    return pd.DataFrame(columns=columns).to_csv(index=False).encode()

def json_bytes(name,fallback):
    data=existing_bytes(name)
    if data is not None:
        return data
    return json.dumps(fallback,indent=2).encode()

st.title("⬇️ Downloads")
st.caption("Trading records, scanner data and sector classification.")
st.subheader("Trading Data")

# Four downloads are ALWAYS rendered. If a runtime file has not been created,
# the user still gets a valid empty/current export instead of a missing button.
with st.container(key="download_grid"):
    q1,q2=st.columns(2,gap="small")
    q1.download_button("⬇️ ACTUAL / CAPITAL-MISSED TRADES CSV",csv_bytes("trades.csv",["status","symbol","entry_time","exit_time","pnl","sector"]),"trades.csv","text/csv",width="stretch")
    q2.download_button("⬇️ SCANNER SIGNALS CSV",csv_bytes("signals.csv",["timestamp","symbol","signal","price","sector"]),"signals.csv","text/csv",width="stretch")
    q3,q4=st.columns(2,gap="small")
    q3.download_button("⬇️ BOT STATUS JSON",json_bytes("bot_status.json",{"status":"WAITING","worker_alive":False,"message":"No runtime status file yet."}),"bot_status.json","application/json",width="stretch")
    q4.download_button("⬇️ PAPER ENGINE STATE JSON",json_bytes("paper_engine_state.json",{"open_positions":{},"available_capital":250000}),"paper_engine_state.json","application/json",width="stretch")

st.subheader("🏭 Sector-wise Stock Classification")

# Prepare/load the NIFTY 100 mapping directly so Downloads does not depend on a
# separate worker cycle having already created the sector cache.
try:
    from data.stock_universe import StockUniverse
    from data.sector_store import SectorStore
    universe=StockUniverse().get_dataframe(refresh=False)
    if universe.empty:
        universe=StockUniverse().get_dataframe(refresh=True)
    mapping=SectorStore(universe).load()
except Exception:
    mapping=pd.DataFrame()

if not mapping.empty:
    mapping=mapping.drop_duplicates("Symbol").sort_values(["Sector","Symbol"])
    summary=(mapping.groupby("Sector",dropna=False).agg(Stocks=("Symbol","count")).reset_index().sort_values("Stocks",ascending=False))
    st.success(f"{len(mapping)} NIFTY 100 stocks classified across {len(summary)} sectors.")
    st.dataframe(summary,width="stretch",hide_index=True)

    # Two sector downloads: complete stock list + sector count summary.
    s1,s2=st.columns(2,gap="small")
    s1.download_button("⬇️ SECTOR-WISE STOCK LIST CSV",mapping.to_csv(index=False).encode(),"sector_wise_stock_list.csv","text/csv",width="stretch")
    s2.download_button("⬇️ SECTOR SUMMARY CSV",summary.to_csv(index=False).encode(),"sector_summary.csv","text/csv",width="stretch")

    st.markdown("**Stocks classified by sector**")
    st.dataframe(mapping[[c for c in ["Sector","Symbol","SectorSource"] if c in mapping.columns]],width="stretch",hide_index=True)
else:
    st.warning("Sector mapping is not available yet. The page will retry from the NIFTY 100 universe on the next refresh.")
