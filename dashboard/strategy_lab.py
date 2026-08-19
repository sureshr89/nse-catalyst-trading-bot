"""Unified S1-S5 comparison and signal analytics."""
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"
STRATEGIES={
"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
def _read(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()
def _strategy_col(df):
 if df.empty:return None
 for c in df.columns:
  if str(c).lower().replace(" ","_") in {"strategy","strategy_id","setup","system"}:return c
 return None
def _stats():
 trades=_read("trades.csv"); signals=_read("signals.csv")
 tc=_strategy_col(trades); sc=_strategy_col(signals)
 rows=[]
 for sid,name in STRATEGIES.items():
  t=trades[trades[tc].astype(str).str.upper().str.startswith(sid)] if tc else pd.DataFrame()
  s=signals[signals[sc].astype(str).str.upper().str.startswith(sid)] if sc else pd.DataFrame()
  result_col=next((c for c in t.columns if str(c).lower() in {"result","outcome","status"}),None)
  rcol=next((c for c in t.columns if str(c).lower() in {"r","r_multiple","net_r","pnl_r"}),None)
  pnlcol=next((c for c in t.columns if str(c).lower() in {"pnl","p&l","profit_loss","net_pnl"}),None)
  vals=pd.to_numeric(t[rcol],errors="coerce").dropna() if rcol else pd.Series(dtype=float)
  wins=int((vals>0).sum()) if not vals.empty else (int(t[result_col].astype(str).str.upper().isin(["WIN","WON","PROFIT"]).sum()) if result_col else 0)
  losses=int((vals<0).sum()) if not vals.empty else (int(t[result_col].astype(str).str.upper().isin(["LOSS","LOST"]).sum()) if result_col else 0)
  net_r=float(vals.sum()) if not vals.empty else None
  maxdd=float((vals.cumsum()-vals.cumsum().cummax()).min()) if not vals.empty else None
  pnl=float(pd.to_numeric(t[pnlcol],errors="coerce").sum()) if pnlcol else None
  rows.append({"Strategy":sid,"Name":name,"Signals":len(s),"Taken":len(t),"Not Taken":max(len(s)-len(t),0),"Wins":wins,"Losses":losses,"Win Rate":(wins/(wins+losses)*100) if wins+losses else None,"Net R":net_r,"Net P&L":pnl,"Max DD (R)":maxdd})
 return pd.DataFrame(rows)
def render_strategy_lab():
 st.markdown("## ⚖️ S1–S5 Strategy Comparison")
 st.caption("One comparison view for all five strategies. Signal, entry/exit timing and performance are calculated from the stored signal/trade ledger; no performance numbers are invented.")
 d=_stats()
 display=d.copy();
 for c in ["Win Rate"]:
  display[c]=display[c].map(lambda x:f"{x:.1f}%" if pd.notna(x) else "—")
 for c in ["Net R","Net P&L","Max DD (R)"]:
  display[c]=display[c].map(lambda x:f"{x:.2f}" if pd.notna(x) else "—")
 st.dataframe(display[["Strategy","Signals","Taken","Not Taken","Wins","Losses","Win Rate","Net R","Net P&L","Max DD (R)"]],width="stretch",hide_index=True)
 if d["Signals"].sum()==0:
  st.info("No verified strategy signal/trade ledger is available yet. The comparison will populate automatically when signals and trades are recorded.")
 else:
  a,b=st.columns(2)
  with a: st.markdown("**Win-rate comparison**"); st.bar_chart(d.set_index("Strategy")["Win Rate"].fillna(0),height=240)
  with b: st.markdown("**Signals vs taken**"); st.bar_chart(d.set_index("Strategy")[["Signals","Taken","Not Taken"]],height=240)
  st.markdown("**Net R comparison**"); st.bar_chart(d.set_index("Strategy")["Net R"].fillna(0),height=240)
 st.markdown("### ⏱️ Signal / Entry / Exit Timing")
 if not _read("signals.csv").empty:
  s=_read("signals.csv"); cols=[c for c in s.columns if str(c).lower() in {"timestamp","time","signal_time","entry_time","exit_time","strategy","strategy_id","signal","side","entry","sl","stop_loss","target","exit","status"}]
  st.dataframe(s[cols].tail(50) if cols else s.tail(50),width="stretch",hide_index=True)
 else: st.info("Signal timing ledger is empty.")
 st.markdown("### 📖 Strategy Theory")
 theory={"S1":"Sweep PDH/PDL liquidity and reclaim the open; confirmation and master breadth/sector alignment required.","S2":"Break PDH/PDL, retest the broken level and confirm continuation; avoid chasing the initial break.","S3":"Sweep the opposite PDH/PDL side and reclaim/reject the open; use breadth and sector alignment as the master filter.","S4":"Break a previously formed intraday high/low with confirmation; do not use an unformed current extreme.","S5":"Direct PDH/PDL breakout with previous-candle confirmation and full 500/500 master alignment."}
 for sid,name in STRATEGIES.items():
  with st.expander(f"{sid} • {name}",expanded=False):
   st.write(theory[sid]);st.write("**Entry:** defined setup + confirmation. **SL:** setup/swing invalidation. **Target:** 1.25R. **Entry window:** 09:45–14:00 IST. **Square-off:** 15:00 IST. **Gate:** NIFTY 500 + sector + A/D; 500/500 breadth required.")
