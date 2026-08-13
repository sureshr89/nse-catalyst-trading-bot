from pathlib import Path
import pandas as pd
import streamlit as st
from io import BytesIO
ROOT=Path(__file__).resolve().parent.parent
st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.title("⬇️ Download Trading Data")
st.caption("Export the persistent strategy records for later research and the full three-month study.")
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
st.subheader("Complete Excel Research Workbook")
try:
    out=BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        actual.to_excel(writer,index=False,sheet_name="Actual Trades")
        missed.to_excel(writer,index=False,sheet_name="Capital Missed")
        signals.to_excel(writer,index=False,sheet_name="All Signals")
        trades.to_excel(writer,index=False,sheet_name="All Trades")
    st.download_button("📘 DOWNLOAD COMPLETE EXCEL",data=out.getvalue(),file_name="nse_catalyst_complete_research.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
except Exception as exc:st.error(f"Excel export unavailable: {type(exc).__name__}: {exc}")
st.divider();st.write(f"Signals: **{len(signals):,}**  •  Actual trades: **{len(actual):,}**  •  Capital-missed: **{len(missed):,}**")
