"""Mobile-first S1-S5 comparison: one numeric table, then comparison charts, then theory."""
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"
STRATEGIES={"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}
def _read(name):
 p=OUTPUTS/name
 try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
 except Exception:return pd.DataFrame()
def _col(df,names):
 if df.empty:return None
 wanted={str(x).lower().replace(" ","_") for x in names}
 return next((c for c in df.columns if str(c).lower().replace(" ","_") in wanted),None)
def _stats():
 t=_read("trades.csv");s=_read("signals.csv");tc=_col(t,["strategy","strategy_id","setup","system"]);sc=_col(s,["strategy","strategy_id","setup","system"]);rows=[]
 for sid,name in STRATEGIES.items():
  tt=t[t[tc].astype(str).str.upper().str.startswith(sid)] if tc else pd.DataFrame();ss=s[s[sc].astype(str).str.upper().str.startswith(sid)] if sc else pd.DataFrame();rc=_col(tt,["result","outcome","status"]);rcol=_col(tt,["r","r_multiple","net_r","pnl_r"]);pcol=_col(tt,["pnl","p&l","profit_loss","net_pnl"]);vals=pd.to_numeric(tt[rcol],errors="coerce").dropna() if rcol else pd.Series(dtype=float);wins=int((vals>0).sum()) if not vals.empty else int(tt[rc].astype(str).str.upper().isin(["WIN","WON","PROFIT"]).sum()) if rc else 0;loss=int((vals<0).sum()) if not vals.empty else int(tt[rc].astype(str).str.upper().isin(["LOSS","LOST"]).sum()) if rc else 0;netr=float(vals.sum()) if not vals.empty else 0.0;pnl=float(pd.to_numeric(tt[pcol],errors="coerce").sum()) if pcol else 0.0;dd=float((vals.cumsum()-vals.cumsum().cummax()).min()) if not vals.empty else 0.0;rows.append({"Strategy":sid,"Signals":len(ss),"Taken":len(tt),"Not Taken":max(len(ss)-len(tt),0),"Wins":wins,"Losses":loss,"Win %":wins/(wins+loss)*100 if wins+loss else 0.0,"Net R":netr,"P&L":pnl,"Max DD":dd})
 return pd.DataFrame(rows)
def render_strategy_lab():
 st.markdown("## ⚖️ S1–S5 STRATEGY COMPARISON")
 st.caption("All five strategies • one view • numbers first • charts second")
 d=_stats()
 st.dataframe(d[["Strategy","Signals","Taken","Not Taken","Wins","Losses","Win %","Net R","P&L","Max DD"]],width="stretch",hide_index=True)
 st.markdown("### 📊 Comparison Charts")
 if d["Signals"].sum()==0: st.info("No verified signal/trade history yet. Performance remains 0 until real records are generated.")
 else:
  st.bar_chart(d.set_index("Strategy")[["Win %"]],height=220)
  st.bar_chart(d.set_index("Strategy")[["Signals","Taken","Not Taken"]],height=220)
  st.bar_chart(d.set_index("Strategy")[["Net R"]],height=220)
  st.bar_chart(d.set_index("Strategy")[["Max DD"]],height=220)
 st.markdown("### ⏱️ SIGNAL → ENTRY → EXIT")
 s=_read("signals.csv")
 if not s.empty:
  cols=[c for c in s.columns if str(c).lower().replace(" ","_") in {"timestamp","time","signal_time","entry_time","exit_time","strategy","strategy_id","signal","side","entry","sl","stop_loss","target","exit","status"}]
  st.dataframe(s[cols].tail(30) if cols else s.tail(30),width="stretch",hide_index=True)
 else: st.info("No signals recorded yet.")
 st.markdown("### 📖 STRATEGY THEORY")
 theory={"S1":"Sweep PDH/PDL liquidity and reclaim the open. Require confirmation and master breadth/sector alignment.","S2":"Break PDH/PDL, retest the broken level and confirm continuation. Do not chase the first break.","S3":"Sweep the opposite PDH/PDL side and reclaim/reject the open with breadth and sector confirmation.","S4":"Break a previously formed intraday high/low with confirmation; current unformed extremes are not references.","S5":"Direct PDH/PDL breakout with previous-candle confirmation and full 500/500 master alignment."}
 for sid,name in STRATEGIES.items():
  with st.expander(f"{sid} • {name}"):
   st.write(theory[sid]);st.write("**Entry:** setup + confirmation. **SL:** setup invalidation. **Target:** 1.25R. **Entry:** 09:45–14:00 IST. **Square-off:** 15:00 IST. **Gate:** NIFTY 500 + sector + A/D + verified 500/500 breadth.")
