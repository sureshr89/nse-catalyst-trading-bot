"""NSE Catalyst production dashboard.

Presentation-only dashboard for the NIFTY 500 paper-trading engine.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from config.settings import MIN_DATA_COVERAGE_COUNT
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
STRATEGIES = ["S1", "S2", "S3", "S4", "S5"]
PALETTE = {"S1": ("#16a34a", "↩️", "PDH/PDL SWEEP REVERSAL"), "S2": ("#0284c7", "🔁", "BREAKOUT + RETEST"), "S3": ("#d97706", "🎯", "INSIDE RANGE REVERSAL"), "S4": ("#7c3aed", "⚡", "INTRADAY BREAKOUT"), "S5": ("#e11d48", "🚀", "PDH/PDL BREAKOUT")}

def read_csv(name):
    path = OUTPUTS / name
    try: return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception: return pd.DataFrame()

def num(value, default=0.0):
    try:
        value=float(value); return value if pd.notna(value) else default
    except Exception: return default

def fmt(value):
    if value is None or value == "" or (isinstance(value,float) and pd.isna(value)): return "—"
    try: return f"{float(value):,.2f}"
    except Exception: return str(value)

def pct(value):
    if value is None or value == "" or (isinstance(value,float) and pd.isna(value)): return "—"
    try: return f"{float(value):,.2f}%"
    except Exception: return str(value)

def first(row,*names,default=""):
    if row is None: return default
    for name in names:
        if name in row.index:
            value=row.get(name)
            if value is not None and str(value).strip() not in {"","nan","NaT"}: return value
    return default

def metric_card(label,value,emphasis=""):
    color={"buy":"#15803d","sell":"#dc2626","wait":"#b45309"}.get(emphasis,"#172033")
    return f'<div style="background:#f8fbff;border:1px solid #d7e4f2;border-radius:12px;padding:12px 13px;min-height:76px;box-sizing:border-box;box-shadow:0 1px 3px rgba(15,23,42,.06);"><div style="font-size:10px;font-weight:800;color:#718096;text-transform:uppercase;letter-spacing:.04em;">{label}</div><div style="font-size:18px;font-weight:900;color:{color};margin-top:7px;line-height:1.15;">{value}</div></div>'

def metric_grid(items): return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;width:100%;margin-bottom:8px;">'+"".join(items)+'</div>'

def strategy_card(strategy,state,state_color,cells):
    accent,icon,subtitle=PALETTE[strategy]
    details="".join(f'<div style="background:#eef4fa;border-radius:8px;padding:8px 9px;min-width:0;"><div style="font-size:8px;font-weight:850;color:#718096;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div><div style="font-size:12px;font-weight:900;color:#172033;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{value or "—"}</div></div>' for label,value in cells)
    return f'<div style="background:#f8fbff;border:1px solid #d7e4f2;border-radius:12px;border-top:3px solid {accent};padding:12px 13px;margin:9px 0;box-sizing:border-box;box-shadow:0 2px 7px rgba(15,23,42,.07);"><div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;"><div style="display:flex;align-items:center;gap:8px;min-width:0;"><span style="font-size:20px;">{icon}</span><div><div style="font-size:17px;font-weight:950;color:{accent};line-height:1;">{strategy}</div><div style="font-size:9px;font-weight:800;color:#718096;letter-spacing:.04em;margin-top:4px;">{subtitle}</div></div></div><span style="font-size:9px;font-weight:900;color:{state_color};background:#eef4fa;border:1px solid #d7e4f2;border-radius:999px;padding:6px 9px;white-space:nowrap;">{state}</span></div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:6px;">{details}</div></div>'

def strategy_name_mask(df,strategy):
    if df.empty: return pd.Series(False,index=df.index)
    cols=[c for c in ["strategy","strategy_name","signal","setup_type"] if c in df.columns]; mask=pd.Series(False,index=df.index)
    for col in cols:
        vals=df[col].astype(str).str.upper().str.strip(); mask |= vals.eq(strategy) | vals.str.startswith(strategy+" ")
    return mask

def strategy_rows(df,strategy): return df[strategy_name_mask(df,strategy)].copy() if not df.empty else df

def performance_stats(df,strategy):
    rows=strategy_rows(df,strategy)
    if rows.empty: return {"trades":0,"open":0,"wins":0,"losses":0,"win_rate":0.0,"pnl":0.0}
    pnl=pd.to_numeric(rows["pnl"],errors="coerce").fillna(0.0) if "pnl" in rows else pd.Series(0.0,index=rows.index)
    status=rows["status"].astype(str).str.upper().str.strip() if "status" in rows else pd.Series("",index=rows.index)
    exit_time=rows["exit_time"].astype(str).str.strip() if "exit_time" in rows else pd.Series("",index=rows.index)
    closed=status.eq("CLOSED") | exit_time.ne("")
    if "exit_price" in rows: closed |= rows["exit_price"].astype(str).str.strip().ne("")
    open_count=int((~closed).sum()); wins=int((closed & pnl.gt(0)).sum()); losses=int((closed & pnl.lt(0)).sum()); decided=wins+losses
    return {"trades":len(rows),"open":open_count,"wins":wins,"losses":losses,"win_rate":wins/decided*100 if decided else 0.0,"pnl":float(pnl.sum())}

def performance_card(strategy,stats,cumulative=False):
    accent,icon,subtitle=PALETTE[strategy]; pnl=stats["pnl"]; pnl_color="#15803d" if pnl>0 else "#dc2626" if pnl<0 else "#64748b"; label="CUMULATIVE" if cumulative else "TODAY"
    cells=[("OPEN",stats["open"],"#172033"),("TRADES",stats["trades"],"#172033"),("WINS",stats["wins"],"#15803d"),("LOSSES",stats["losses"],"#dc2626"),("WIN RATE",f'{stats["win_rate"]:.1f}%',"#172033"),(f'{label} P&L',f'₹{pnl:,.2f}',pnl_color)]
    body="".join(f'<div style="background:#eef4fa;border-radius:8px;padding:7px;"><div style="color:#718096;font-size:8px;font-weight:800;">{k}</div><div style="font-size:13px;font-weight:900;color:{c};margin-top:3px;">{v}</div></div>' for k,v,c in cells)
    return f'<div style="background:#f8fbff;border:1px solid #d7e4f2;border-radius:12px;border-top:3px solid {accent};padding:12px;box-sizing:border-box;box-shadow:0 2px 7px rgba(15,23,42,.07);"><div style="display:flex;align-items:center;justify-content:space-between;gap:7px;margin-bottom:9px;"><div style="font-size:18px;font-weight:950;color:{accent};">{icon} {strategy}</div><div style="font-size:8px;font-weight:850;color:#718096;text-align:right;">{subtitle}</div></div><div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;">{body}</div></div>'

st.markdown("""<style>
.stApp{background:#000000!important;color:#ffffff!important}
.block-container{max-width:1450px;padding:.7rem .8rem 2rem}
.section-title{font-size:20px;font-weight:950;color:#ffffff;margin:18px 0 9px}
.performance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
@media (max-width:1100px){.performance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:700px){.block-container{padding:.55rem .55rem 1.5rem}.performance-grid{grid-template-columns:1fr}}
</style>""",unsafe_allow_html=True)

@st.fragment(run_every="15s")
def live_dashboard():
    now=datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured,dhan_status,index_quote
        market=BREADTH.snapshot(force=False); raw_index=index_quote("NIFTY 500")
        if raw_index:
            ltp=num(raw_index.get("LTP")); net=num(raw_index.get("NetChange")); prev=num(raw_index.get("PreviousClose"))
            if ltp>0 and prev>0: market.update({"nifty500_ltp":ltp,"nifty500_net_change":net,"nifty500_previous_close":prev,"nifty500_change_pct":net/prev*100})
        dhan_ok=dhan_configured(); api_status=dhan_status()
    except Exception as exc:
        market={"complete":False,"sector_complete":False,"evaluated":0,"sector_priced":0,"nifty500_change_pct":None,"ad_ratio":None,"advances":0,"declines":0,"unchanged":0,"positive_sectors":0,"negative_sectors":0,"reason":f"{type(exc).__name__}: {exc}","quote_rows":pd.DataFrame()}; dhan_ok=False; api_status={"ok":False,"message":str(exc)}; raw_index=None
    trades_all=read_csv("trades.csv"); signals_all=read_csv("signals.csv"); today=now.date()
    def today_rows(df,columns):
        if df.empty:return df
        col=next((c for c in columns if c in df.columns),None)
        if not col:return df
        d=pd.to_datetime(df[col],errors="coerce",utc=True)
        try:d=d.dt.tz_convert(IST)
        except Exception:pass
        return df[d.dt.date==today]
    trades_today=today_rows(trades_all,["exit_time","entry_time","market_entry_time","trigger_entry_time"]); signals_today=today_rows(signals_all,["timestamp","entry_time","logged_at"])
    complete=bool(market.get("complete")); sector_complete=bool(market.get("sector_complete")); n=market.get("nifty500_change_pct") if complete else None; ad=market.get("ad_ratio") if complete else None; evaln=int(market.get("evaluated",0) or 0) if complete else 0; sp=int(market.get("sector_priced",0) or 0) if sector_complete else 0; advances=int(market.get("advances",0) or 0) if complete else 0; declines=int(market.get("declines",0) or 0) if complete else 0; unchanged=int(market.get("unchanged",0) or 0) if complete else 0; positive_sectors=int(market.get("positive_sectors",0) or 0) if sector_complete else 0; negative_sectors=int(market.get("negative_sectors",0) or 0) if sector_complete else 0
    quote_rows=market.get("quote_rows"); quote_count=len(quote_rows) if isinstance(quote_rows,pd.DataFrame) else evaln; buy=bool(complete and sector_complete and num(n)>0 and positive_sectors>negative_sectors and num(ad)>1); sell=bool(complete and sector_complete and num(n)<0 and negative_sectors>positive_sectors and num(ad,2)<1); bias="🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"
    st.markdown('<div style="font-size:30px;font-weight:950;color:#ffffff;">📊 NSE Catalyst — Master Dashboard</div>',unsafe_allow_html=True); st.markdown(f'<div style="font-size:12px;color:#94a3b8;margin-bottom:12px;">NIFTY 500 • PAPER TRADING ONLY • Dhan • {now.strftime("%d %b %Y %H:%M:%S")} IST • auto refresh 15s</div>',unsafe_allow_html=True); st.markdown('<div class="section-title">🎯 MARKET ALIGNMENT</div>',unsafe_allow_html=True)
    index_display=pct(n)
    if raw_index and market.get("nifty500_ltp") is not None:index_display=f'{fmt(market.get("nifty500_ltp"))} {"+" if num(market.get("nifty500_net_change"))>=0 else ""}{fmt(market.get("nifty500_net_change"))} ({pct(n)})'
    st.markdown(metric_grid([metric_card("NIFTY 500",index_display if complete else "WAITING"),metric_card("ADVANCES",advances if complete else "WAITING"),metric_card("DECLINES",declines if complete else "WAITING"),metric_card("A/D RATIO",fmt(ad) if complete and ad is not None else "WAITING"),metric_card("POSITIVE SECTORS",positive_sectors if sector_complete else "WAITING"),metric_card("NEGATIVE SECTORS",negative_sectors if sector_complete else "WAITING")]),unsafe_allow_html=True)
    st.markdown(metric_grid([metric_card("UNCHANGED",unchanged if complete else "WAITING"),metric_card("LIVE COVERAGE",f"{evaln}/500"),metric_card("SECTOR DATA",f"{sp}/500"),metric_card("98% GATE","PASS" if evaln>=MIN_DATA_COVERAGE_COUNT else "BLOCK","buy" if evaln>=MIN_DATA_COVERAGE_COUNT else "wait"),metric_card("MASTER BIAS",bias,"buy" if buy else "sell" if sell else "wait")]),unsafe_allow_html=True)
    status_ok=bool(complete and quote_count>=MIN_DATA_COVERAGE_COUNT); reason=str(market.get("reason") or "").replace("<","&lt;").replace(">","&gt;"); status=f'<b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if status_ok else "WAIT/ERROR"} • Live snapshot {quote_count}/500 • refresh 15s';
    if not status_ok:status+=f' • {api_status.get("message") or reason or "incomplete quote data"}'
    bg="#092417" if status_ok else "#281313"; border="#28633f" if status_ok else "#6b3333"; text="#e8eef7" if status_ok else "#fecaca"; st.markdown(f'<div style="margin:8px 0;padding:11px 13px;background:{bg};border:1px solid {border};border-radius:11px;color:{text};font-size:13px;">{status}</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚡ S1–S5 — TODAY</div>',unsafe_allow_html=True)
    for strategy in STRATEGIES:
        tr=strategy_rows(trades_today,strategy); sg=strategy_rows(signals_today,strategy); row=tr.iloc[-1] if not tr.empty else None; signal_row=sg.iloc[-1] if not sg.empty else None
        if row is not None:
            status_text=str(first(row,"status",default="OPEN")).upper(); state="CLOSED" if status_text=="CLOSED" or first(row,"exit_time") not in {"",None} else "TRADE OPEN"; cells=[("Stock",first(row,"symbol","stock")),("BUY / SELL",first(row,"buy_sell","side","signal")),("Signal Time",first(row,"trigger_entry_time","entry_time","market_entry_time")),("Entry",fmt(first(row,"entry","entry_price"))),("Stop Loss",fmt(first(row,"stop_loss"))), ("Target",fmt(first(row,"target"))), ("Exit",fmt(first(row,"exit_price","exit"))), ("P&L",fmt(first(row,"pnl"))), ("Risk / Reward",fmt(first(row,"rr","reward","risk_reward"))), ("Quantity",fmt(first(row,"quantity"))), ("Exit Reason",first(row,"exit_reason") or "—")]
        elif signal_row is not None:
            state="SIGNAL"; cells=[("Stock",first(signal_row,"symbol","stock")),("BUY / SELL",first(signal_row,"buy_sell","side","signal")),("Signal Time",first(signal_row,"timestamp","entry_time","logged_at")),("Entry",fmt(first(signal_row,"entry","entry_price"))),("Stop Loss",fmt(first(signal_row,"stop_loss"))), ("Target",fmt(first(signal_row,"target"))), ("Exit","—"),("P&L","—"),("Risk / Reward",fmt(first(signal_row,"risk_reward","rr","reward"))),("Quantity",fmt(first(signal_row,"quantity"))),("Exit Reason","—")]
        else:
            state="WAITING"; cells=[("Stock","—"),("BUY / SELL","—"),("Signal Time","—"),("Entry","—"),("Stop Loss","—"),("Target","—"),("Exit","—"),("P&L","—"),("Risk / Reward","—"),("Quantity","—"),("Exit Reason","—")]
        state_color="#15803d" if state=="CLOSED" else "#0284c7" if state=="SIGNAL" else "#b45309" if state=="TRADE OPEN" else "#64748b"; st.markdown(strategy_card(strategy,state,state_color,cells),unsafe_allow_html=True)
    today_stats={s:performance_stats(trades_today,s) for s in STRATEGIES}; cumulative_stats={s:performance_stats(trades_all,s) for s in STRATEGIES}
    st.markdown('<div class="section-title">📅 TODAY — ALL POSITIONS</div>',unsafe_allow_html=True); st.markdown('<div style="font-size:11px;color:#94a3b8;margin-bottom:9px;">S1–S5: open positions, trades, wins, losses, win rate and today P&amp;L.</div>',unsafe_allow_html=True); st.markdown('<div class="performance-grid">'+''.join(performance_card(s,today_stats[s]) for s in STRATEGIES)+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 CUMULATIVE — ALL DAYS</div>',unsafe_allow_html=True); st.markdown('<div style="font-size:11px;color:#94a3b8;margin-bottom:9px;">Complete historical S1–S5 performance across all available trading days.</div>',unsafe_allow_html=True); st.markdown('<div class="performance-grid">'+''.join(performance_card(s,cumulative_stats[s],cumulative=True) for s in STRATEGIES)+'</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">📥 DOWNLOAD</div>',unsafe_allow_html=True); st.download_button("⬇️ Download Master CSV",trades_all.to_csv(index=False).encode("utf-8"),"nse_catalyst_master.csv","text/csv",use_container_width=True,key="master_csv"); st.markdown('<div class="section-title">💡 DAILY TRADING TIP</div>',unsafe_allow_html=True); tips=["Follow the setup, not the emotion.","Protect capital first; profits come second.","Wait for confirmation before entering.","One disciplined trade is better than many emotional trades.","Never chase a missed entry."]; st.markdown(f'<div style="background:#101b2b;border:1px solid #294367;border-radius:12px;padding:14px;font-size:16px;font-weight:850;color:#ffffff;">💡 {tips[now.date().toordinal()%len(tips)]}</div>',unsafe_allow_html=True)

def render_dashboard(): live_dashboard()
if __name__ == "__main__": render_dashboard()