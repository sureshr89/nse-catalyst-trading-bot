"""Strategy 2 single-page command center: same structure as Strategy 1."""
from pathlib import Path
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import io
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from bot_runner import ensure_bot_running
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from dashboard.strategy2_data import status, diagnostics, state, gaps, signals, trades, format_price, format_pct, STARTING_CAPITAL
from market.price_data import PriceData
from strategy.contracts import strategy_metadata

INDIA_TZ=ZoneInfo("Asia/Kolkata"); ENTRY_START,ENTRY_END="09:45","14:00"; MIN_RISK,MAX_RISK=1400.0,1500.0
st.set_page_config(page_title="NSE Catalyst | Strategy 2",page_icon="🔴",layout="wide",initial_sidebar_state="collapsed")
st_autorefresh(interval=5000,key="s2_single_page_live"); st.markdown(load_css(),unsafe_allow_html=True); render_nav()

def age(v):
    try:
        x=datetime.fromisoformat(str(v).replace("Z","+00:00")); x=x.replace(tzinfo=INDIA_TZ) if x.tzinfo is None else x
        return max(0,int((datetime.now(timezone.utc)-x.astimezone(timezone.utc)).total_seconds()))
    except Exception:return None

def cards(items): st.markdown("<div class='metric-grid'>"+"".join(f"<div class='metric-card'><small>{a}</small><b>{b}</b></div>" for a,b in items)+"</div>",unsafe_allow_html=True)

def chart(fig,key,height=300):
    fig.update_layout(height=height,margin=dict(l=8,r=8,t=48,b=8),template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False},key=key)

def numeric(df,cols):
    for c in cols:
        if c not in df.columns: df[c]=0.0
        df[c]=pd.to_numeric(df[c],errors="coerce").fillna(0.0)
    return df

try: ensure_bot_running()
except Exception: pass
s=status() or {}; d=diagnostics() or {}; paper=state() or {}; gap=gaps(); sig=signals(); all_trades=trades(); now=datetime.now(INDIA_TZ); positions=paper.get("open_positions",{}) or {}; scan_age=age(d.get("timestamp")); hb=age(s.get("heartbeat")); worker_ok=bool(s.get("worker_alive")) and hb is not None and hb<=90; clock=now.strftime("%H:%M"); window="PREPARE" if clock<ENTRY_START else "ACTIVE" if clock<=ENTRY_END else "CLOSED"; meta=strategy_metadata("STRATEGY_2")

st.title("🔴 Strategy 2")
st.caption(f"{meta['name']} • {meta['version']} • Single-page command center • LIVE LTP entry / SL / target • no candle-close confirmation • {now.strftime('%d %b %Y %H:%M:%S')} IST")
cards([("WORKER","🟢 RUNNING" if worker_ok else "🔴 STALE"),("AVAILABLE CAPITAL",format_price(s.get("available_capital",STARTING_CAPITAL))),("ENTRY WINDOW",window),("OPEN POSITIONS",len(positions)),("REALIZED DAILY P&L",format_price(s.get("daily_pnl",0))),("LAST SCAN",f"{scan_age}s ago" if scan_age is not None else "—"),("EXIT MONITOR","LIVE / ~5s UI")])
if s.get("last_error"): st.error(str(s["last_error"]))

with st.expander("🔎 Live Scanner & Trading",expanded=True):
    today_sig=sig.copy()
    if not today_sig.empty:
        dc="entry_time" if "entry_time" in today_sig.columns else "timestamp" if "timestamp" in today_sig.columns else None
        if dc:
            z=pd.to_datetime(today_sig[dc],errors="coerce"); z=z.dt.tz_localize(INDIA_TZ) if z.dt.tz is None else z.dt.tz_convert(INDIA_TZ); today_sig=today_sig.loc[z.dt.date.eq(now.date())]
    approved_today=today_sig[today_sig["approved"].astype(str).str.lower().isin({"true","1","yes"})] if not today_sig.empty and "approved" in today_sig.columns else today_sig.iloc[0:0]
    cards([("CANDIDATES",d.get("candidates",0)),("BUY CANDIDATES",d.get("buy_candidates",0)),("SELL CANDIDATES",d.get("sell_candidates",0)),("BUY QUALIFIED",d.get("buy_qualified",0)),("SELL QUALIFIED",d.get("sell_qualified",0)),("FINAL SIGNALS",d.get("signals",0)),("RISK APPROVED",len(approved_today)),("REJECTIONS",sum((d.get("rejections",{}) or {}).values()))])

with st.expander("📋 Scanner Pipeline & Alignment",expanded=False):
    pipeline=pd.DataFrame([("Universe",d.get("candidates",0),"NIFTY 500 opening GAP candidates","DATA"),("Extension",int(d.get("buy_candidates",0) or 0)+int(d.get("sell_candidates",0) or 0),"Live price extends beyond Today's Open","SETUP"),("Reversal qualified",int(d.get("buy_qualified",0) or 0)+int(d.get("sell_qualified",0) or 0),"Live price returns through Today's Open","LIVE LTP"),("Risk adjusted",d.get("risk_adjusted",0),"₹1,400–₹1,500 actual-risk band","RISK"),("Final approved",d.get("signals",0),"Entry + risk gate accepted","ENTRY")],columns=["Stage","Count","Rule / Data","Type"]); st.dataframe(pipeline,width="stretch",hide_index=True)

with st.expander("⏳ GAP Candidates / Setups",expanded=False):
    if gap.empty: st.info("No Strategy 2 GAP candidates currently available.")
    else:
        b=gap.copy(); cols=[c for c in ["Symbol","TodayOpen","PDH","PDL","PreviousDayClose","GapPercentFromPreviousClose","GapType","OpeningSetup"] if c in b.columns]; st.dataframe(b[cols].head(100),width="stretch",hide_index=True,height=340)

with st.expander("🚨 Today's Approved Signals",expanded=False):
    today=approved_today.copy()
    if not today.empty:
        cols=[c for c in ["symbol","signal","entry_time","entry","stop_loss","target","quantity","actual_risk","risk_reward","gap_percent","priority_rank"] if c in today.columns]; st.dataframe(today[cols].tail(25).iloc[::-1],width="stretch",hide_index=True)
    else: st.info("No approved signals today.")

with st.expander("📍 Open Paper Positions",expanded=True):
    if positions:
        rows=[]; pdx=PriceData()
        for symbol,p in positions.items():
            try: live=pdx.get_latest_live_price(symbol,max_age_seconds=3); ltp=live.get("Close") if live else None
            except Exception: live=None; ltp=None
            side=str(p.get("signal","")).upper(); entry=p.get("entry"); qty=float(p.get("quantity",0) or 0); pnl=None
            try: pnl=((float(ltp)-float(entry))*qty) if side=="BUY" else ((float(entry)-float(ltp))*qty)
            except Exception: pass
            rows.append({"Strategy":"STRATEGY_2","Stock":symbol,"Side":side,"Entry":format_price(entry),"LTP":format_price(ltp),"Live P&L":format_price(pnl),"SL":format_price(p.get("stop_loss")),"Target":format_price(p.get("target")),"Qty":qty,"Risk":format_price(p.get("actual_risk",p.get("risk"))),"Entry Time":p.get("entry_time","—"),"Exit Time":p.get("exit_time","—")})
        st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
    else: st.info("No open Strategy 2 paper positions.")

with st.expander("📊 Analysis — complete before-trade + after-trade analysis",expanded=True):
    closed=numeric(all_trades.copy(),["pnl","entry","exit","exit_price","stop_loss","target","quantity","actual_risk","risk_reward","rr","gap_percent","mae","mfe"])
    if not closed.empty and "status" in closed.columns: closed=closed[closed["status"].astype(str).str.upper().eq("CLOSED")].copy()
    if not closed.empty:
        closed=closed.reset_index(drop=True); closed["Trade #"]=range(1,len(closed)+1); closed["Result"]=closed.pnl.map(lambda x:"WIN" if x>0 else "LOSS" if x<0 else "FLAT"); closed["Cumulative P&L"]=closed.pnl.cumsum(); closed["Peak"]=closed["Cumulative P&L"].cummax(); closed["Drawdown"]=closed["Cumulative P&L"]-closed["Peak"]
    wins=int((closed.pnl>0).sum()) if not closed.empty else 0; losses=int((closed.pnl<0).sum()) if not closed.empty else 0; net=float(closed.pnl.sum()) if not closed.empty else 0; gp=float(closed.loc[closed.pnl>0,"pnl"].sum()) if not closed.empty else 0; gl=abs(float(closed.loc[closed.pnl<0,"pnl"].sum())) if not closed.empty else 0; wr=wins/len(closed)*100 if len(closed) else 0; pf=gp/gl if gl else 0; dd=abs(float(closed.Drawdown.min())) if not closed.empty else 0
    cards([("Decision Records",len(sig)),("Closed Trades",len(closed)),("Wins / Losses",f"{wins} / {losses}"),("Net P&L",format_price(net)),("Equity",format_price(STARTING_CAPITAL+net)),("Win Rate",f"{wr:.1f}%"),("Profit Factor",f"{pf:.2f}"),("Max Drawdown",format_price(dd))])
    st.markdown("**Before Trade — Setup & Decision**")
    pre=numeric(sig.copy(),["entry","stop_loss","target","actual_risk","risk_reward","gap_percent","today_open","today_high","today_low","nifty500_change_pct"])
    if not pre.empty:
        cols=[c for c in ["timestamp","symbol","signal","today_open","pdh","pdl","gap_percent","entry","stop_loss","target","quantity","actual_risk","risk_reward","approved","reason"] if c in pre.columns]; st.dataframe(pre[cols].tail(300).iloc[::-1],width="stretch",hide_index=True,height=300) if cols else st.dataframe(pre.tail(300).iloc[::-1],width="stretch",hide_index=True,height=300)
        a,b=st.columns(2)
        with a: chart(px.histogram(pre,x="actual_risk",nbins=14,title="Actual Risk Distribution"),"s2_before_risk")
        with b: chart(px.histogram(pre,x="risk_reward",nbins=14,title="Risk:Reward Distribution"),"s2_before_rr")
        a,b=st.columns(2)
        with a: chart(px.histogram(pre,x="gap_percent",nbins=14,title="Opening GAP Distribution"),"s2_before_gap")
        with b:
            if "signal" in pre.columns: chart(px.bar(pre.signal.astype(str).str.upper().value_counts().rename_axis("Signal").reset_index(name="Decisions"),x="Signal",y="Decisions",text="Decisions",title="BUY vs SELL Decisions"),"s2_before_side")
    else: st.info("No Strategy 2 decision records yet.")
    st.markdown("**After Trade — Outcome & Performance**")
    if closed.empty: st.info("No completed Strategy 2 trades yet.")
    else:
        a,b=st.columns(2)
        with a: chart(px.line(closed,x="Trade #",y="Cumulative P&L",markers=True,title="Cumulative P&L"),"s2_after_cum")
        with b: chart(px.area(closed,x="Trade #",y="Drawdown",title="Drawdown"),"s2_after_dd")
        a,b=st.columns(2)
        with a: chart(px.histogram(closed,x="pnl",nbins=14,title="P&L Distribution"),"s2_after_pnl")
        with b: chart(px.bar(closed.groupby("Result",as_index=False).pnl.sum(),x="Result",y="pnl",text="pnl",title="P&L by Outcome"),"s2_after_result")
        if "symbol" in closed.columns:
            stock=closed.groupby("symbol",as_index=False).agg(Trades=("symbol","size"),PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100)).sort_values("PnL",ascending=False); chart(px.bar(stock.head(20),x="symbol",y="PnL",text="Trades",title="Stocks by P&L"),"s2_after_stock",340); st.dataframe(stock,width="stretch",hide_index=True,height=280)
        with st.expander("📋 Trade Taken Details — Entry / Exit / P&L",expanded=False):
            cols=[c for c in ["strategy","symbol","signal","entry","entry_time","market_entry_time","trigger_entry_time","exit","exit_price","exit_time","stop_loss","target","quantity","actual_risk","pnl","exit_reason","status"] if c in closed.columns]; st.dataframe(closed[cols].tail(500).iloc[::-1] if cols else closed.tail(500).iloc[::-1],width="stretch",hide_index=True,height=450)
    with st.expander("⚡ Authoritative Strategy Rules",expanded=False): st.dataframe(pd.DataFrame(list(meta["rules"])+[("Risk","₹1,400–₹1,500 actual risk"),("Entry window","09:45–14:00 IST"),("Monitoring","LIVE LTP • no candle-close confirmation"),("Square-off","15:00 IST")],columns=["Rule","Definition"]),width="stretch",hide_index=True)

with st.expander("📋 Decision Records",expanded=False):
    st.dataframe(sig.tail(500).iloc[::-1],width="stretch",hide_index=True,height=400) if not sig.empty else st.info("No decision records.")

with st.expander("⬇️ Downloads — master monthly file",expanded=False):
    st.caption("One Strategy 2 master workbook with ALL TRADES and month-wise sheets.")
    if all_trades.empty: st.info("No trade history available yet.")
    else:
        try:
            out=io.BytesIO()
            with pd.ExcelWriter(out,engine="openpyxl") as writer:
                all_trades.to_excel(writer,index=False,sheet_name="ALL TRADES")
                dates=pd.to_datetime(all_trades.get("entry_time",pd.Series(dtype=str)),errors="coerce")
                months=dates.dt.strftime("%Y-%m") if not dates.empty else pd.Series(dtype=str)
                for month in months.dropna().unique(): all_trades.loc[months.eq(month)].to_excel(writer,index=False,sheet_name=str(month)[:31])
            st.download_button("⬇️ DOWNLOAD S2 MASTER EXCEL",data=out.getvalue(),file_name="NSE_CATALYST_S2_MASTER.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")
        except Exception as e: st.error(f"Master workbook unavailable: {e}")
    st.download_button("⬇️ S2 TRADES CSV",data=all_trades.to_csv(index=False).encode(),file_name="strategy2_trades.csv",mime="text/csv",width="stretch")
    st.download_button("⬇️ S2 SIGNALS CSV",data=sig.to_csv(index=False).encode(),file_name="strategy2_signals.csv",mime="text/csv",width="stretch")

st.caption(f"Heartbeat: {s.get('heartbeat','—')} • Last scan: {d.get('timestamp','—')} • UI refresh: 5s")
render_daily_footer()
