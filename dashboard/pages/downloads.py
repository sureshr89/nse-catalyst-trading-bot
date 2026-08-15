from pathlib import Path
import sys,json
from io import BytesIO
from copy import copy
from datetime import datetime
from dateutil.relativedelta import relativedelta
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import streamlit as st
import pandas as pd
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from master_data import build_master_data

st.set_page_config(page_title="NSE Catalyst | Downloads",page_icon="⬇️",layout="wide")
st.markdown(load_css(),unsafe_allow_html=True);render_nav(24)
try:ensure_bot_running()
except Exception as error:st.warning(f"Worker launcher: {type(error).__name__}: {error}")

def read_csv(name):
    try:
        path=ROOT/"outputs"/name;return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def file_bytes(name,fallback):
    path=ROOT/"outputs"/name
    try:return path.read_bytes() if path.exists() else pd.DataFrame(columns=fallback).to_csv(index=False).encode("utf-8")
    except Exception:return pd.DataFrame(columns=fallback).to_csv(index=False).encode("utf-8")

def json_bytes(name,fallback):
    path=ROOT/"outputs"/name
    try:return path.read_bytes() if path.exists() else json.dumps(fallback,indent=2).encode()
    except Exception:return json.dumps(fallback,indent=2).encode()

def canonical_trades(frame):
    if frame.empty:return frame
    if "trade_id" in frame.columns:
        ids=frame["trade_id"].astype(str).str.strip();with_id=frame[ids.ne("")&ids.ne("nan")].drop_duplicates("trade_id",keep="last");without_id=frame[~(ids.ne("")&ids.ne("nan"))].copy();keys=[c for c in ["symbol","signal","entry_time","entry"] if c in without_id.columns];without_id=without_id.drop_duplicates(keys,keep="last") if keys else without_id.drop_duplicates();return pd.concat([with_id,without_id],ignore_index=True)
    keys=[c for c in ["symbol","signal","entry_time","entry"] if c in frame.columns];return frame.drop_duplicates(keys,keep="last") if keys else frame.drop_duplicates()

def months():
    first=datetime.now().replace(day=1);return [(first-relativedelta(months=i)).strftime("%Y-%m") for i in range(6)]

def month_filter(frame,month,cols):
    if frame.empty:return frame
    for c in cols:
        if c in frame.columns:
            values=pd.to_datetime(frame[c],errors="coerce")
            if values.notna().any():return frame.loc[values.dt.strftime("%Y-%m").eq(month)].copy()
    return frame.iloc[0:0].copy()

def monthly_excel(month):
    daily=read_csv("MASTER_DAILY_STOCK_DATA.csv");trades=canonical_trades(read_csv("MASTER_TRADES.csv"));summary=read_csv("MASTER_DAILY_SUMMARY.csv");signals=read_csv("signals.csv");output=BytesIO()
    sheets={"Daily Stock Data":(daily,["TradeDate","DataSnapshotIST"]),"All Trades":(trades,["TradeDate","entry_time","exit_time"]),"Daily Summary":(summary,["TradeDate"]),"Gap Board":(daily,["TradeDate"]),"Signals":(signals,["timestamp","entry_time"])}
    with pd.ExcelWriter(output,engine="openpyxl") as writer:
        for name,(frame,cols) in sheets.items():
            data=month_filter(frame,month,cols)
            if name=="Gap Board" and not data.empty:
                keep=[c for c in ["TradeDate","Symbol","PreviousClose","TodayOpen","Gap","GapPercent","GapType","PDH","PDL","GapFromPreviousClose","GapPercentFromPreviousClose","DataSnapshotIST"] if c in data.columns];data=data[keep]
            if data.empty:data=pd.DataFrame({"Status":[f"No records for {month}"]})
            data.to_excel(writer,sheet_name=name,index=False);ws=writer.book[name];ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
            for col in ws.columns:
                vals=[str(x.value or "") for x in list(col)[:300]];ws.column_dimensions[col[0].column_letter].width=min(max(max((len(v) for v in vals),default=10)+2,10),32)
                for cell in ws[1]:cell.font=copy(cell.font);cell.font=cell.font.copy(bold=True)
        pd.DataFrame([["Month",month],["Strategy","NIFTY 500 market filter + stock PDH/PDL + Today's Open reversal"],["BUY","Open above PDH → price closes below PDH → later candle opens below Today's Open and closes above Today's Open → NIFTY 500 ≥ +0.25%"],["SELL","Open below PDL → price closes above PDL → later candle opens above Today's Open and closes below Today's Open → NIFTY 500 ≤ −0.25%"],["Risk","BUY SL = PDH; SELL SL = PDL; Target = 1.25 × entry-to-SL risk; max risk ₹1,500/trade; max 2 positions; daily max loss ₹3,000"],["Generated",pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d %H:%M:%S IST")]],columns=["Field","Value"]).to_excel(writer,sheet_name="README",index=False)
    output.seek(0);return output.getvalue()

try:build_master_data()
except Exception as error:st.warning(f"Master data refresh warning: {type(error).__name__}: {error}")

st.title("⬇️ Downloads");st.caption("Trading records, daily market data, gap board and strategy results.")
trades=canonical_trades(read_csv("trades.csv"));signals=read_csv("signals.csv");gaps=read_csv("gap_analysis.csv");months_list=months();master=canonical_trades(read_csv("MASTER_TRADES.csv"));daily=read_csv("MASTER_DAILY_STOCK_DATA.csv")
st.subheader("⭐ Master Trading Data — Last 6 Months")
rows=[]
for month in months_list:rows.append({"Month":pd.Timestamp(month+"-01").strftime("%B %Y"),"File":f"NSE_CATALYST_MASTER_TRADING_DATA_{month}.xlsx","Records":len(month_filter(master,month,["TradeDate","entry_time","exit_time"]))+len(month_filter(daily,month,["TradeDate"]))})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
selected=st.selectbox("📅 Select a month",months_list,format_func=lambda x:pd.Timestamp(x+"-01").strftime("%B %Y"))
st.download_button("⬇️ DOWNLOAD MASTER EXCEL",data=monthly_excel(selected),file_name=f"NSE_CATALYST_MASTER_TRADING_DATA_{selected}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")
st.subheader("📁 Trading Data")
st.download_button("⬇️ TRADES CSV",data=trades.to_csv(index=False).encode() if not trades.empty else file_bytes("trades.csv",["status","symbol","signal","entry_time","exit_time","entry","stop_loss","target","quantity","pnl"]),file_name="nifty500_trades.csv",mime="text/csv",width="stretch")
st.download_button("⬇️ SIGNALS CSV",data=signals.to_csv(index=False).encode() if not signals.empty else file_bytes("signals.csv",["timestamp","symbol","signal","entry","stop_loss","target","setup_type","approved","reason"]),file_name="nifty500_signals.csv",mime="text/csv",width="stretch")
st.download_button("⬇️ PREMARKET GAP BOARD CSV",data=gaps.to_csv(index=False).encode() if not gaps.empty else file_bytes("gap_analysis.csv",["Symbol","PreviousClose","TodayOpen","Gap","GapPercent","GapType","PDH","PDL"]),file_name="nifty500_premarket_gap_board.csv",mime="text/csv",width="stretch")
st.subheader("⚙️ Bot Records")
st.download_button("⬇️ BOT STATUS JSON",data=json_bytes("bot_status.json",{"status":"WAITING","worker_alive":False}),file_name="nifty500_bot_status.json",mime="application/json",width="stretch")
st.download_button("⬇️ PAPER STATE JSON",data=json_bytes("paper_engine_state.json",{"open_positions":{},"available_capital":250000}),file_name="nifty500_paper_state.json",mime="application/json",width="stretch")
st.subheader("📌 Premarket Gap Board")
if not gaps.empty and "GapType" in gaps.columns:
    g=gaps.copy();g["GapPercent"]=pd.to_numeric(g["GapPercent"],errors="coerce");a,b=st.columns(2)
    with a:st.markdown("**🟢 Gap Up — Open > PDH**");st.dataframe(g[g["GapType"].eq("GAP_UP")].sort_values("GapPercent",ascending=False).head(30),width="stretch",hide_index=True,height=350)
    with b:st.markdown("**🔴 Gap Down — Open < PDL**");st.dataframe(g[g["GapType"].eq("GAP_DOWN")].sort_values("GapPercent").head(30),width="stretch",hide_index=True,height=350)
else:st.info("Gap board will appear after current market data is available.")
st.caption("Downloads are generated from recorded paper-trading and market-data files. No live orders are placed from this page.")
render_daily_footer()
