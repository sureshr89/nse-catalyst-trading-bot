from pathlib import Path
import pandas as pd
import streamlit as st
from io import BytesIO
ROOT=Path(__file__).resolve().parent.parent
st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.title("⬇️ Download Trading Data")
st.caption("Export actual trades, capital-missed outcomes, scanner records, sector classification, and the complete research workbook.")
def load(name):
    p=ROOT/"outputs"/name
    try:return pd.read_csv(p)
    except Exception:return pd.DataFrame()
signals=load("signals.csv"); trades=load("trades.csv")
actual=trades[trades["status"].astype(str).str.upper()=="CLOSED"].copy() if not trades.empty and "status" in trades.columns else trades.copy()
missed=trades[trades["status"].astype(str).str.upper().isin(["MISSED_CAPITAL_OPEN","MISSED_CAPITAL_CLOSED"])].copy() if not trades.empty and "status" in trades.columns else pd.DataFrame()
def dl(label,df,name):st.download_button(label=label,data=df.to_csv(index=False).encode("utf-8"),file_name=name,mime="text/csv",use_container_width=True)
a,b,c=st.columns(3)
with a:dl("⬇️ Actual Trades CSV",actual,"actual_trades.csv")
with b:dl("⬇️ Capital-Missed CSV",missed,"capital_missed_trades.csv")
with c:dl("⬇️ All Signals CSV",signals,"all_scanner_signals.csv")

# Sector-wise NIFTY 100 stock classification.
sector_map=pd.DataFrame()
try:
    from data.stock_universe import StockUniverse
    from data.sector_store import SectorStore
    universe=StockUniverse().get_dataframe(refresh=False)
    sector_map=SectorStore(universe).load()
except Exception:
    sector_map=pd.DataFrame()
if not sector_map.empty:
    sector_map=sector_map.copy()
    sector_map["Symbol"]=sector_map["Symbol"].astype(str).str.upper().str.strip()
    sector_map["Sector"]=sector_map["Sector"].fillna("UNKNOWN").astype(str).str.strip().replace("","UNKNOWN")
    sector_summary=sector_map.groupby("Sector",as_index=False).agg(**{"Stock Count":("Symbol","nunique"),"Stocks":("Symbol",lambda s:", ".join(sorted(set(s.astype(str)))))})
    sector_summary=sector_summary.sort_values(["Stock Count","Sector"],ascending=[False,True]).reset_index(drop=True)
    st.subheader("Sector-wise Stock Classification")
    st.caption(f"{sector_map['Symbol'].nunique()} stocks classified across {len(sector_summary)} sectors. Stock Count shows how many NIFTY 100 stocks belong to each sector.")
    st.dataframe(sector_summary,use_container_width=True,hide_index=True)
    dl("⬇️ DOWNLOAD SECTOR-WISE STOCK LIST CSV",sector_summary,"sector_wise_stock_list.csv")
else:
    sector_summary=pd.DataFrame(columns=["Sector","Stock Count","Stocks"])
    st.info("Sector classification will appear when the NIFTY 100 sector mapping is available.")

st.subheader("Complete Excel Research Workbook")
try:
    out=BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        actual.to_excel(writer,index=False,sheet_name="Actual Trades")
        missed.to_excel(writer,index=False,sheet_name="Capital Missed")
        signals.to_excel(writer,index=False,sheet_name="All Signals")
        trades.to_excel(writer,index=False,sheet_name="All Trades")
        if not sector_map.empty:
            sector_summary.to_excel(writer,index=False,sheet_name="Sector Summary")
            sector_map.to_excel(writer,index=False,sheet_name="Sector Stock Mapping")
    st.download_button("📘 DOWNLOAD COMPLETE EXCEL",data=out.getvalue(),file_name="nse_catalyst_complete_research.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
except Exception as exc:st.error(f"Excel export unavailable: {type(exc).__name__}: {exc}")
st.divider();st.write(f"Signals: **{len(signals):,}**  •  Actual trades: **{len(actual):,}**  •  Capital-missed: **{len(missed):,}**  •  Sectors: **{len(sector_summary):,}**  •  Classified stocks: **{len(sector_map):,}**")
