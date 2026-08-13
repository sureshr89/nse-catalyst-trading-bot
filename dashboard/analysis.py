"""Read-only visual strategy research dashboard."""
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
ROOT=Path(__file__).resolve().parent.parent
TRADES=ROOT/"outputs"/"trades.csv"; SIGNALS=ROOT/"outputs"/"signals.csv"; STARTING_CAPITAL=250000.0
st.set_page_config(page_title="NSE Catalyst | Analysis",page_icon="📊",layout="wide")
st.markdown('''<style>
.block-container{padding-top:.7rem;padding-bottom:2rem;max-width:1500px}
/* Plotly charts are display-only: block mouse, pointer, wheel and touch gestures. */
[data-testid="stPlotlyChart"],.js-plotly-plot,.plot-container,.svg-container{pointer-events:none!important;touch-action:none!important;user-select:none!important;-webkit-user-select:none!important}
[data-testid="stPlotlyChart"] canvas,[data-testid="stPlotlyChart"] svg{pointer-events:none!important;touch-action:none!important}
</style>''',unsafe_allow_html=True)
def read_csv(path):
    try:return pd.read_csv(path)
    except (FileNotFoundError,pd.errors.EmptyDataError,OSError):return pd.DataFrame()
def num(df,col,default=0.0):
    if col not in df.columns:df[col]=default
    df[col]=pd.to_numeric(df[col],errors="coerce").fillna(default)
def prep(df):
    df=df.copy()
    if df.empty:return df
    for c in ["entry","stop_loss","target","quantity","risk","reward","rr","pnl","actual_risk","position_value","risk_reward"]:num(df,c)
    if all(c in df for c in ["risk","entry","stop_loss","quantity"]):
        m=df.risk<=0;df.loc[m,"risk"]=(df.loc[m,"entry"]-df.loc[m,"stop_loss"]).abs()*df.loc[m,"quantity"]
    if all(c in df for c in ["reward","target","entry","quantity"]):
        m=df.reward<=0;df.loc[m,"reward"]=(df.loc[m,"target"]-df.loc[m,"entry"]).abs()*df.loc[m,"quantity"]
    m=df.risk>0;df.loc[m,"rr"]=df.loc[m,"reward"]/df.loc[m,"risk"];df["Result"]=df.pnl.apply(lambda x:"WIN" if x>0 else "LOSS" if x<0 else "FLAT");return df
def stats(df):
    if df.empty:return {"Trades":0,"Wins":0,"Losses":0,"Flat":0,"Win Rate %":0.0,"P&L":0.0,"Avg P&L":0.0,"Avg Win":0.0,"Avg Loss":0.0,"Expectancy":0.0,"Profit Factor":0.0,"Avg Risk":0.0,"Avg R:R":0.0}
    p=pd.to_numeric(df.pnl,errors="coerce").fillna(0.0);w=p[p>0];l=p[p<0];gp=float(w.sum());gl=abs(float(l.sum()));return {"Trades":len(df),"Wins":int((p>0).sum()),"Losses":int((p<0).sum()),"Flat":int((p==0).sum()),"Win Rate %":round(float((p>0).mean()*100),2),"P&L":round(float(p.sum()),2),"Avg P&L":round(float(p.mean()),2),"Avg Win":round(float(w.mean()),2) if not w.empty else 0.0,"Avg Loss":round(float(l.mean()),2) if not l.empty else 0.0,"Expectancy":round(float(p.mean()),2),"Profit Factor":round(gp/gl,3) if gl else 0.0,"Avg Risk":round(float(df.risk.mean()),2),"Avg R:R":round(float(df.rr.mean()),3)}
def grouped(df,col):
    if df.empty or col not in df:return pd.DataFrame()
    rows=[]
    for v,g in df.groupby(col,dropna=False):
        r=stats(g);r[col]=str(v) if pd.notna(v) and str(v) else "UNKNOWN";rows.append(r)
    return pd.DataFrame(rows).sort_values("P&L",ascending=False) if rows else pd.DataFrame()
def chart(fig,height=340):
    fig.update_layout(height=height,margin=dict(l=10,r=10,t=55,b=12),font=dict(size=12),title_font=dict(size=16))
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False,"responsive":True,"scrollZoom":False,"doubleClick":False,"dragmode":False,"staticPlot":True},key=f"static_{id(fig)}")
def pie(df,col,title,height=330):
    if df.empty or col not in df:return
    x=df[col].fillna("UNKNOWN").astype(str).value_counts().reset_index();x.columns=[col,"Count"];chart(px.pie(x,names=col,values="Count",hole=.45,title=title),height)
trades=prep(read_csv(TRADES));signals=read_csv(SIGNALS)
if not trades.empty and "status" in trades:
    s=trades.status.astype(str).str.upper();actual=prep(trades[s.eq("CLOSED")].copy());missed=prep(trades[s.isin(["MISSED_CAPITAL_OPEN","MISSED_CAPITAL_CLOSED"])].copy())
else:actual=missed=pd.DataFrame()
missed_closed=missed[missed.status.astype(str).str.upper().eq("MISSED_CAPITAL_CLOSED")].copy() if not missed.empty else pd.DataFrame();a=stats(actual);m=stats(missed_closed)
ledger=pd.DataFrame();time_col=next((c for c in ["exit_time","entry_time","timestamp"] if c in actual.columns),None)
if time_col and not actual.empty:
    ledger=actual.copy();ledger["Date"]=pd.to_datetime(ledger[time_col],errors="coerce").dt.date;ledger=ledger[ledger.Date.notna()].copy();ledger=ledger.groupby("Date",as_index=False).pnl.sum().sort_values("Date");ledger["Cumulative P&L"]=ledger.pnl.cumsum();ledger["Equity"]=STARTING_CAPITAL+ledger["Cumulative P&L"];ledger["Result"]=ledger.pnl.apply(lambda x:"Profit" if x>0 else "Loss" if x<0 else "Flat")
monthly=pd.DataFrame()
if not ledger.empty:
    monthly=ledger.copy();monthly["Month"]=pd.to_datetime(monthly.Date).dt.to_period("M").astype(str);monthly=monthly.groupby("Month",as_index=False).pnl.sum().sort_values("Month");monthly["Cumulative P&L"]=monthly.pnl.cumsum();monthly["Equity"]=STARTING_CAPITAL+monthly["Cumulative P&L"];monthly["Return %"]=monthly.pnl/STARTING_CAPITAL*100
st.markdown('<h1>📊 Strategy Analysis</h1>',unsafe_allow_html=True);st.markdown('<p>Official performance uses only closed actual trades. Capital-missed trades are always hypothetical and never change actual P&L.</p>',unsafe_allow_html=True)
pnl=a["P&L"];equity=STARTING_CAPITAL+pnl;ret=pnl/STARTING_CAPITAL*100
st.subheader("💰 Overall Account Performance");c1,c2,c3,c4=st.columns(4);c1.metric("Fixed Starting Capital",f"₹{STARTING_CAPITAL:,.0f}");c2.metric("Overall P&L",f"₹{pnl:,.2f}");c3.metric("Current Equity",f"₹{equity:,.2f}");c4.metric("Overall Return",f"{ret:+.2f}%");c1,c2,c3,c4=st.columns(4);c1.metric("Trading Days",len(ledger));c2.metric("Profitable Days",int((ledger.pnl>0).sum()) if not ledger.empty else 0);c3.metric("Loss Days",int((ledger.pnl<0).sum()) if not ledger.empty else 0);c4.metric("Closed Trades",a["Trades"])
st.subheader("📅 Daily & Monthly P&L")
if not ledger.empty:
    left,right=st.columns(2)
    with left:chart(px.bar(ledger,x="Date",y="pnl",title="Daily P&L"),360)
    with right:chart(px.line(ledger,x="Date",y="Cumulative P&L",markers=True,title="Cumulative P&L"),360)
    left,right=st.columns(2)
    with left:chart(px.bar(monthly,x="Month",y="pnl",title="Monthly Net P&L"),350)
    with right:chart(px.line(monthly,x="Month",y="Equity",markers=True,title="Equity Over Months"),350)
    st.dataframe(ledger.rename(columns={"pnl":"Daily P&L"})[["Date","Daily P&L","Cumulative P&L","Equity","Result"]].iloc[::-1],use_container_width=True,hide_index=True)
else:st.info("No dated closed actual trades yet.")
st.subheader("📌 Trade & Strategy KPIs");c1,c2,c3,c4=st.columns(4);c1.metric("Actual Trades",a["Trades"]);c2.metric("Win Rate",f'{a["Win Rate %"]:.1f}%');c3.metric("Average P&L / Trade",f'₹{a["Avg P&L"]:,.2f}');c4.metric("Profit Factor",f'{a["Profit Factor"]:.2f}');c1,c2,c3,c4=st.columns(4);c1.metric("Wins",a["Wins"]);c2.metric("Losses",a["Losses"]);c3.metric("Average Win",f'₹{a["Avg Win"]:,.2f}');c4.metric("Average Loss",f'₹{a["Avg Loss"]:,.2f}')
# Remaining research charts use the same chart() function, so every chart receives staticPlot and touch-blocking CSS.
st.subheader("📈 Trade-Level Performance")
if not actual.empty:
    curve=actual.copy();tc=next((c for c in ["exit_time","entry_time"] if c in curve),None)
    if tc:curve["_time"]=pd.to_datetime(curve[tc],errors="coerce");curve=curve.sort_values("_time",na_position="last")
    curve["Trade #"]=range(1,len(curve)+1);curve["Cumulative P&L"]=curve.pnl.cumsum();curve["Drawdown"]=curve["Cumulative P&L"]-curve["Cumulative P&L"].cummax();left,right=st.columns(2)
    with left:chart(px.line(curve,x="Trade #",y="Cumulative P&L",markers=True,title="Cumulative Actual P&L"),350)
    with right:chart(px.bar(curve,x="Trade #",y="pnl",title="Individual Trade P&L"),350)
    left,right=st.columns(2)
    with left:chart(px.line(curve,x="Trade #",y="Drawdown",markers=True,title="Drawdown"),330)
    with right:chart(px.line(curve,x="Trade #",y="pnl",markers=True,title="Trade P&L Sequence"),330)
st.subheader("🎯 Outcome Analysis")
if not actual.empty:
    left,right=st.columns(2)
    with left:pie(actual.assign(Outcome=actual.Result),"Outcome","Actual Win / Loss / Flat")
    with right:pie(actual,"exit_reason","Actual Exit Reasons")
st.subheader("🏷️ Where the Strategy Works")
if not actual.empty:
    gs=grouped(actual,"signal");ge=grouped(actual,"exit_reason");left,right=st.columns(2)
    with left:
        if not gs.empty:chart(px.bar(gs,x="signal",y="P&L",text="Trades",title="P&L by BUY / SELL"),340)
    with right:
        if not ge.empty:chart(px.bar(ge,x="exit_reason",y="P&L",text="Trades",title="P&L by Exit Reason"),340)
    ss=grouped(actual,"symbol")
    if not ss.empty:
        left,right=st.columns(2)
        with left:chart(px.bar(ss.head(20),x="symbol",y="P&L",text="Trades",title="Top 20 Stocks by Actual P&L"),380)
        with right:st.dataframe(ss[["symbol","Trades","Wins","Losses","Win Rate %","P&L"]],use_container_width=True,hide_index=True,height=380)
st.subheader("⚖️ Risk & R:R Analysis")
if not actual.empty:
    left,right=st.columns(2)
    with left:chart(px.scatter(actual,x="risk",y="pnl",size="quantity" if "quantity" in actual else None,hover_name="symbol",hover_data=["signal","rr"],title="Risk vs Actual P&L"),360)
    with right:chart(px.scatter(actual,x="rr",y="pnl",hover_name="symbol",hover_data=["signal","risk"],title="R:R vs Actual P&L"),360)
st.subheader("⏱️ Signal & Trade Timing")
if signals.empty:st.info("No scanner signals available for timing analysis yet.")
else:
    sig=signals.copy()
    if "timestamp" in sig:
        sig["_time"]=pd.to_datetime(sig.timestamp,errors="coerce");sig=sig[sig._time.notna()].copy()
        if not sig.empty:
            sig["Minute"]=sig._time.dt.strftime("%H:%M");counts=sig.groupby("Minute").size().reset_index(name="Signals");chart(px.bar(counts,x="Minute",y="Signals",title="Scanner Signal Spikes by Time"),350)
st.subheader("🌐 Market / Sector / Setup Analysis")
if not actual.empty:
    for col in ["nifty100_direction","sector_direction","stock_today_direction","previous_day_direction","setup_type"]:
        if col in actual.columns and actual[col].notna().any():
            t=grouped(actual,col)
            if not t.empty:chart(px.bar(t,x=col,y="P&L",text="Trades",title=f"Actual P&L by {col.replace('_',' ').title()}"),330)
st.subheader("🆚 Actual vs Capital-Missed");comparison=pd.DataFrame([{"Category":"Actual trades",**a},{"Category":"Capital-missed resolved",**m}]);st.dataframe(comparison,use_container_width=True,hide_index=True)
st.subheader("📋 Detailed Research Data");tab1,tab2,tab3=st.tabs(["Actual Trades","Capital-Missed","Scanner Signals"])
with tab1:
    if not actual.empty:st.dataframe(actual.iloc[::-1],use_container_width=True,hide_index=True)
with tab2:
    if not missed.empty:st.dataframe(missed.iloc[::-1],use_container_width=True,hide_index=True)
with tab3:
    if not signals.empty:st.dataframe(signals.iloc[::-1],use_container_width=True,hide_index=True)
st.divider();st.caption("Read-only analysis. Actual P&L and hypothetical capital-missed P&L remain separate.")