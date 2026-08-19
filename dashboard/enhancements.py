"""Clean, mobile-first NSE Catalyst dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
OUTPUTS=ROOT/"outputs"
IST=ZoneInfo("Asia/Kolkata")

def _csv(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def _sector_frame(q,u):
    if q is None or q.empty or u is None or u.empty:return pd.DataFrame()
    sym_q=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in q.columns),None)
    sym_u=next((c for c in ["Symbol","SEM_TRADING_SYMBOL","TradingSymbol"] if c in u.columns),None)
    if not sym_q or not sym_u:return pd.DataFrame()
    sector_col=next((c for c in ["Sector","sector","Industry"] if c in u.columns),None)
    if not sector_col:return pd.DataFrame()
    m=u[[sym_u,sector_col]].copy();m.columns=["Symbol","Sector"]
    x=q.copy();x["Symbol"]=x[sym_q].astype(str).str.upper().str.replace(".NS","",regex=False)
    m["Symbol"]=m["Symbol"].astype(str).str.upper().str.replace(".NS","",regex=False)
    if "change_pct" not in x.columns:
        if {"LTP","PreviousClose"}.issubset(x.columns):
            pc=pd.to_numeric(x["PreviousClose"],errors="coerce");x["change_pct"]=(pd.to_numeric(x["LTP"],errors="coerce")-pc)/pc*100
        elif {"Close","PreviousClose"}.issubset(x.columns):
            pc=pd.to_numeric(x["PreviousClose"],errors="coerce");x["change_pct"]=(pd.to_numeric(x["Close"],errors="coerce")-pc)/pc*100
        else:return pd.DataFrame()
    x["change_pct"]=pd.to_numeric(x["change_pct"],errors="coerce")
    x=m.merge(x[["Symbol","change_pct"]],on="Symbol",how="inner").dropna(subset=["change_pct"])
    if x.empty:return pd.DataFrame()
    return x.groupby("Sector").agg(Stocks=("Symbol","count"),ChangePct=("change_pct","mean"),Advances=("change_pct",lambda z:int((z>0).sum())),Declines=("change_pct",lambda z:int((z<0).sum()))).reset_index().sort_values("ChangePct",ascending=False)

def _master_journal(q,live,now):
    if len(q)<500:return
    OUTPUTS.mkdir(exist_ok=True);p=OUTPUTS/"master_journal_cumulative.csv"
    row={"Date":str(now.date()),"NIFTY500ChangePct":live.get("nifty500_change_pct"),"ADRatio":live.get("ad_ratio"),"Advances":live.get("advances"),"Declines":live.get("declines"),"Unchanged":live.get("unchanged"),"PositiveSectors":live.get("positive_sectors"),"NegativeSectors":live.get("negative_sectors"),"SectorAlignmentPct":live.get("sector_alignment_pct"),"Coverage":len(q),"DataSource":"Dhan"}
    try:
        old=pd.read_csv(p) if p.exists() else pd.DataFrame()
        if not old.empty and "Date" in old:old=old[old["Date"].astype(str)!=str(now.date())]
        pd.concat([old,pd.DataFrame([row])],ignore_index=True).to_csv(p,index=False)
    except Exception:pass

def _archive_daily_stock_data(q,live,sec,now):
    if now.hour<16 or len(q)<500:return False
    OUTPUTS.mkdir(exist_ok=True);p=OUTPUTS/"master_cumulative.csv";day=str(now.date())
    try:
        x=q.copy();x.insert(0,"Date",day);x["DataSource"]="Dhan";x["ArchiveTimeIST"]=now.strftime("%Y-%m-%d %H:%M:%S")
        if "Symbol" not in x.columns:
            c=next((c for c in ["SEM_TRADING_SYMBOL","TradingSymbol"] if c in x.columns),None)
            if c:x["Symbol"]=x[c]
        old=pd.read_csv(p) if p.exists() else pd.DataFrame()
        if not old.empty and "Date" in old:old=old[old["Date"].astype(str)!=day]
        pd.concat([old,x],ignore_index=True).to_csv(p,index=False);_master_journal(q,live,now);return True
    except Exception:return False

def render_enhancements():
    now=datetime.now(IST)
    st.markdown("""<style>
    .block-container{padding:.55rem .7rem 1.3rem;max-width:1180px}
    h1{font-size:1.35rem!important;font-weight:700!important;margin:.2rem 0 .55rem!important;color:#172033!important}
    h2{font-size:1.02rem!important;font-weight:700!important;margin:.7rem 0 .35rem!important;color:#172033!important}
    h3{font-size:.88rem!important;font-weight:650!important;margin:.5rem 0 .28rem!important;color:#344054!important}
    [data-testid="stMetricValue"]{font-size:1.05rem!important;font-weight:700!important;color:#172033!important}
    [data-testid="stMetricLabel"]{font-size:.68rem!important;font-weight:600!important;color:#667085!important}
    .clock{background:#172033;color:#fff;border-radius:10px;padding:9px 11px;margin-bottom:8px;border-left:4px solid #2563EB}
    .clock .t{font-size:1.15rem;font-weight:700;letter-spacing:.01em}.clock .s{font-size:.68rem;color:#cbd5e1}
    .bias{background:#fff;border:1px solid #dfe5ee;border-radius:10px;padding:10px 12px;margin-bottom:9px;color:#172033;box-shadow:0 1px 3px rgba(16,24,40,.05)}
    .bias .title{font-size:.78rem;font-weight:700;color:#667085}.bias .main{font-size:1.12rem;font-weight:750;margin:2px 0}.bias .small{font-size:.68rem;color:#667085}
    .section-card{background:#fff;border:1px solid #e1e7ef;border-radius:10px;padding:7px 9px}
    .tip{background:#eef5ff;border:1px solid #c9dcfb;border-radius:10px;padding:10px;font-size:.84rem;color:#172033}
    [data-testid="stDataFrame"]{border:1px solid #e1e7ef;border-radius:9px;overflow:hidden}
    button{border-radius:8px!important}
    @media(max-width:700px){.block-container{padding:.35rem .45rem .9rem}h1{font-size:1.18rem!important}h2{font-size:.96rem!important}h3{font-size:.84rem!important}[data-testid="stMetricValue"]{font-size:1rem!important}.clock .t{font-size:1.05rem}.stDataFrame{font-size:10px!important}}
    </style>""",unsafe_allow_html=True)
    st.markdown(f"<div class='clock'><div>🕒 LIVE TIME • INDIA</div><div class='t'>{now.strftime('%d %b %Y • %H:%M:%S')} IST</div><div class='s'>Dhan snapshot is independent • dashboard does not refresh the screen just for the clock</div></div>",unsafe_allow_html=True)
    try:
        from market.nifty500_breadth import BREADTH
        from data.stock_universe import StockUniverse
        live=BREADTH.snapshot(force=False);u=StockUniverse().get_dataframe(refresh=False)
    except Exception as e:
        live={"quote_rows":pd.DataFrame(),"reason":str(e)};u=pd.DataFrame()
    q=live.get("quote_rows",pd.DataFrame());q=q if isinstance(q,pd.DataFrame) else pd.DataFrame(q)
    sec=_sector_frame(q,u);cov=len(q);ad=live.get("ad_ratio");chg=live.get("nifty500_change_pct")
    archived=_archive_daily_stock_data(q,live,sec,now) if now.hour>=16 else False
    after_close=now.hour>=16
    if after_close:q_live=pd.DataFrame();sec_live=pd.DataFrame();cov_live=0
    else:q_live=q;sec_live=sec;cov_live=cov
    bull=(not after_close and chg is not None and float(chg)>0 and ad is not None and float(ad)>1 and live.get("sector_alignment_pct",0)>0 and cov_live>=500)
    bear=(not after_close and chg is not None and float(chg)<0 and ad is not None and float(ad)<1 and live.get("sector_alignment_pct",0)<0 and cov_live>=500)
    bias="🟢 BULLISH" if bull else "🔴 BEARISH" if bear else "⚪ WAIT / NO TRADE"
    dhan_time=live.get("last_quote_time","—")
    if after_close:dhan_time="Market closed • archived at 16:00+ IST"
    st.markdown(f"<div class='bias'><div class='title'>🎯 MASTER MARKET BIAS</div><div class='main'>{bias}</div><div>NIFTY 500: {('+'+format(float(chg),'.2f')+'%') if chg is not None and float(chg)>=0 else (format(float(chg),'.2f')+'%' if chg is not None else '—')} &nbsp; • &nbsp; SECTOR: {live.get('sector_alignment_pct','—')} &nbsp; • &nbsp; A/D: {f'{float(ad):.2f}' if ad is not None and pd.notna(ad) else 'WAITING'}</div><div class='small'>Dhan update: {dhan_time} IST &nbsp; • &nbsp; Coverage: {cov_live}/500{' • Daily data archived after 16:00 IST' if after_close else ''}</div></div>",unsafe_allow_html=True)
    try:
        from dashboard.strategy_lab import render_strategy_lab
        render_strategy_lab()
    except Exception as e:st.error(f"Strategy comparison unavailable: {e}")
    tabs=st.tabs(["🟢 LIVE","📚 PAST","📖 THEORY"])
    with tabs[0]:
        if after_close:st.info("Live data is archived after 16:00 IST. The completed session remains in Past and the Master Cumulative CSV.")
        else:
            a,b,c,d=st.columns(4);a.metric("NIFTY 500",f"{float(chg):+.2f}%" if chg is not None else "—");b.metric("A/D",f"{float(ad):.2f}" if ad is not None and pd.notna(ad) else "WAIT");c.metric("Adv / Dec",f"{live.get('advances',0)} / {live.get('declines',0)}");d.metric("Coverage",f"{cov_live}/500")
            if not sec_live.empty:
                st.markdown("#### Sector spikes");st.bar_chart(sec_live.set_index("Sector")["ChangePct"].head(8),height=190)
                with st.expander("Full sector numbers",expanded=False):st.dataframe(sec_live,width="stretch",hide_index=True)
            else:st.info("Sector analysis waits for verified stock prices + sector mapping.")
            with st.expander("500-stock detail",expanded=False):
                if not q_live.empty:st.dataframe(q_live,width="stretch",hide_index=True)
    with tabs[1]:
        try:
            from market.closed_session import load_saved
            pq,past=load_saved()
        except Exception as e:pq=pd.DataFrame();past={"coverage":"0/500","reason":str(e)}
        if not pq.empty:
            ps=_sector_frame(pq,u);a,b,c=st.columns(3);a.metric("Coverage",f"{len(pq)}/500");b.metric("A/D",past.get("ad_ratio","—"));c.metric("Session",past.get("session_date","—"))
            if not ps.empty:
                st.markdown("#### Past sector spikes");st.bar_chart(ps.set_index("Sector")["ChangePct"].head(8),height=190)
                with st.expander("Full past sector numbers",expanded=False):st.dataframe(ps,width="stretch",hide_index=True)
            with st.expander("500-stock past detail",expanded=False):st.dataframe(pq,width="stretch",hide_index=True)
        else:st.info(f"Past session not verified • coverage {past.get('coverage','0/500')}")
    with tabs[2]:
        for sid,name in {"S1":"PDH/PDL Sweep + Open Reclaim","S2":"PDH/PDL Breakout + Retest","S3":"PDL/PDH Sweep + Open Reclaim","S4":"Intraday High/Low Breakout","S5":"Direct PDH/PDL Breakout"}.items():
            with st.expander(f"{sid} • {name}",expanded=False):st.write("Entry → confirmation → SL → target → exit/square-off. Use NIFTY 500 + sector + A/D alignment and verified breadth.")
    st.markdown("### 📥 Downloads")
    cumulative=_csv("master_cumulative.csv")
    if not cumulative.empty:st.download_button("⬇️ Master CSV — Daily Cumulative",cumulative.to_csv(index=False).encode(),"master_cumulative_daily.csv","text/csv",use_container_width=True)
    summary=_csv("master_journal_cumulative.csv")
    if not summary.empty:
        with st.expander("Daily summary CSV",expanded=False):st.download_button("Download daily summary",summary.to_csv(index=False).encode(),"master_journal_summary.csv","text/csv",use_container_width=True)
    st.markdown("### 💡 Daily trading tip")
    tips=["Protect capital first; opportunities return.","A planned trade is better than an emotional trade.","Wait for confirmation; missing one trade is cheaper than forcing one.","Risk small enough to stay in the game.","Let price confirm the idea before committing capital."]
    st.markdown(f"<div class='tip'>💡 <b>{tips[now.date().toordinal()%len(tips)]}</b></div>",unsafe_allow_html=True)
