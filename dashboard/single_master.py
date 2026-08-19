"""Clean live master dashboard for NSE Catalyst.

The page refreshes its complete visible dashboard every 15 seconds. It uses
Dhan breadth/quote data when configured, shows the paper worker heartbeat, and
keeps CSV download controls visible even when there are zero trades.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
STRATEGIES = {
    "S1": "PDH/PDL Sweep + Open Reclaim",
    "S2": "PDH/PDL Breakout + Retest",
    "S3": "Opposite PDH/PDL Sweep + Open Reclaim",
    "S4": "Intraday High/Low Breakout",
    "S5": "Direct PDH/PDL Breakout",
}
st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

def read_csv(name):
    path = OUTPUTS / name
    try: return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception: return pd.DataFrame()

def read_json(name):
    path = OUTPUTS / name
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception: return {}

def num(value, default=None):
    try:
        value = float(value); return value if pd.notna(value) else default
    except (TypeError, ValueError): return default

def pct(value):
    value = num(value); return f"{value:+.2f}%" if value is not None else "—"

def money(value): return f"₹{num(value, 0.0):,.0f}"

def normalize_strategy(value):
    text = str(value).upper().strip()
    if text in STRATEGIES: return text
    if text.startswith("STRATEGY_"): return "S" + text.split("_")[-1]
    return text

def daily_trades(df, day):
    if df.empty: return df
    for col in ("entry_time", "exit_time", "timestamp"):
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce"); return df.loc[dt.dt.date == day].copy()
    return df.iloc[0:0].copy()

def journal_export(trades):
    columns = ["row_type","date","strategy","symbol","side","entry_time","exit_time","entry","exit","exit_price","stop_loss","target","quantity","actual_risk","pnl","exit_reason","nifty500_change_pct","sector_alignment_pct","sector","ad_ratio","ad_coverage","previous_candle_open","previous_candle_close","previous_candle_color","pdh","pdl","today_open","today_high","today_low","entry_reason","exit_rules","notes"]
    if trades.empty: return pd.DataFrame(columns=columns)
    out = trades.copy()
    if "strategy" in out.columns: out["strategy"] = out["strategy"].map(normalize_strategy)
    if "row_type" not in out.columns: out.insert(0, "row_type", "TRADE")
    if "entry_time" in out.columns: out["date"] = pd.to_datetime(out["entry_time"], errors="coerce").dt.date.astype("string")
    else: out["date"] = ""
    for col in columns:
        if col not in out.columns: out[col] = ""
    return out[columns].copy()

@st.fragment(run_every=15)
def render_dashboard():
    now = datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured, dhan_status
        market = BREADTH.snapshot(force=False); dhan_ok = dhan_configured(); api = dhan_status()
    except Exception as exc:
        market = {"complete":False,"sector_complete":False,"reason":f"{type(exc).__name__}: {exc}","evaluated":0,"quote_rows":pd.DataFrame()}; dhan_ok=False; api={"ok":False,"message":str(exc)}
    try:
        from bot_runner import ensure_bot_running
        worker = ensure_bot_running()
    except Exception as exc:
        worker = {"status":"ERROR","message":f"Worker startup failed: {type(exc).__name__}: {exc}","worker_alive":False}
    trades = read_csv("trades.csv"); signals = read_csv("signals.csv"); diagnostics = read_json("scanner_diagnostics.json"); status = read_json("bot_status.json")
    if status: worker = {**worker, **status}
    today = daily_trades(trades, now.date()); pnl = pd.to_numeric(today.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0); wins=int((pnl>0).sum()); losses=int((pnl<0).sum())
    n=market.get("nifty500_change_pct"); sec=market.get("sector_alignment_pct"); ad=market.get("ad_ratio")
    buy=bool(market.get("complete") and market.get("sector_complete") and num(n,0)>0 and num(sec,0)>0 and num(ad,0)>1); sell=bool(market.get("complete") and market.get("sector_complete") and num(n,0)<0 and num(sec,0)<0 and num(ad,2)<1); bias="🟢 BUY ALIGNED" if buy else "🔴 SELL ALIGNED" if sell else "⚪ WAIT — NO TRADE"
    st.markdown("""
    <style>
    .stApp{background:#05070B;color:#F5F7FB}.block-container{max-width:1200px;padding:.65rem .7rem 1.5rem}.hero{background:linear-gradient(135deg,#020406,#07151F,#062B32);border:1px solid #17313A;border-radius:16px;padding:15px 17px;margin-bottom:9px}.hero h1{margin:0;color:#F8FAFC;font-size:1.55rem;font-weight:850}.sub{color:#BFD5DA;font-size:.76rem;margin-top:5px}.live{background:#07151F;border:1px solid #17313A;border-radius:11px;padding:9px 12px;color:#5DE7F5;font-weight:750;font-size:.82rem;margin:7px 0}.section{font-size:1.05rem;font-weight:850;margin:15px 0 7px;color:#F5F7FB}.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.card{background:#0B0F14;border:1px solid #26313D;border-radius:12px;padding:10px;min-height:62px}.lab{font-size:.58rem;color:#9EABB8;text-transform:uppercase;font-weight:750}.val{font-size:.94rem;color:#F5F7FB;font-weight:850;margin-top:4px}.good{color:#20E38A}.bad{color:#FF5C67}.warn{color:#FFD166}.strategy{background:#0B0F14;border:1px solid #26313D;border-left:3px solid #00D9FF;border-radius:12px;padding:10px;margin:6px 0}.strategy b{color:#F5F7FB}.muted{color:#9EABB8;font-size:.72rem}.stDownloadButton button{background:#08242A!important;color:#5DE7F5!important;border:1px solid #00D9FF!important;font-weight:800!important}@media(max-width:850px){.grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.grid{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:1.25rem}.section{font-size:.98rem}}
    </style>""", unsafe_allow_html=True)
    st.markdown(f"<div class='hero'><h1>📊 NSE CATALYST</h1><div class='sub'>NIFTY 500 • PAPER TRADING ONLY • Dhan market gate • S1–S5 • 1 trade / strategy / day</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='live'>🕒 {now.strftime('%d %b %Y • %H:%M:%S')} IST &nbsp;•&nbsp; 🔄 Dashboard + prices refresh every 15 seconds</div>", unsafe_allow_html=True)
    worker_alive=bool(worker.get("worker_alive")); worker_status=str(worker.get("status","UNKNOWN")); st.markdown(f"<div class='live'>🤖 PAPER BOT: <b>{'🟢 RUNNING' if worker_alive else '🔴 NOT RUNNING'}</b> &nbsp;•&nbsp; {worker_status} &nbsp;•&nbsp; {worker.get('message','')}</div>", unsafe_allow_html=True)
    st.markdown("<div class='section'>🎯 MASTER MARKET ALIGNMENT</div>", unsafe_allow_html=True)
    coverage=market.get("evaluated",0)
    cards=[f"<div class='card'><div class='lab'>NIFTY 500</div><div class='val'>{pct(n)}</div></div>",f"<div class='card'><div class='lab'>SECTOR</div><div class='val'>{pct(sec)}</div></div>",f"<div class='card'><div class='lab'>A/D RATIO</div><div class='val'>{num(ad):.2f}</div></div>" if ad is not None else "<div class='card'><div class='lab'>A/D RATIO</div><div class='val'>WAIT</div></div>",f"<div class='card'><div class='lab'>BREADTH</div><div class='val'>{coverage}/500</div></div>",f"<div class='card'><div class='lab'>SECTOR DATA</div><div class='val'>{market.get('sector_priced',0)}/500</div></div>",f"<div class='card'><div class='lab'>MASTER BIAS</div><div class='val {'good' if buy else 'bad' if sell else 'warn'}'>{bias}</div></div>"]
    st.markdown("<div class='grid'>"+"".join(cards)+"</div>",unsafe_allow_html=True); st.caption(f"Dhan configured: {'YES' if dhan_ok else 'NO'} • API: {'PASS' if api.get('ok') else 'WAIT/ERROR'} • {api.get('message','')} • quote request {api.get('received',0)}/{api.get('requested',0)}")
    st.markdown("<div class='section'>⚡ S1–S5 LIVE STATUS</div>",unsafe_allow_html=True)
    counts=diagnostics.get("signals_by_strategy",{}) if isinstance(diagnostics,dict) else {}; daily_counts=diagnostics.get("daily_counts",{}) if isinstance(diagnostics,dict) else {}; open_positions=int(worker.get("open_positions",0) or 0)
    for sid,name in STRATEGIES.items():
        done=int(daily_counts.get(sid,0) or 0); eligible=int(counts.get(sid,0) or 0); state="TRADE DONE" if done else "ELIGIBLE" if eligible else "WAIT"
        st.markdown(f"<div class='strategy'><b>{sid} • {name}</b><div class='muted'>Status: {state} • Today trades: {done}/1 • Current eligible: {eligible} • Open positions: {open_positions}</div></div>",unsafe_allow_html=True)
    st.markdown("<div class='section'>💰 TODAY'S ACTUAL TRADING</div>",unsafe_allow_html=True)
    cards=[f"<div class='card'><div class='lab'>TRADES</div><div class='val'>{len(today)}</div></div>",f"<div class='card'><div class='lab'>WINS</div><div class='val good'>{wins}</div></div>",f"<div class='card'><div class='lab'>LOSSES</div><div class='val bad'>{losses}</div></div>",f"<div class='card'><div class='lab'>WIN RATE</div><div class='val'>{wins/len(pnl)*100:.1f}%</div></div>" if len(pnl) else "<div class='card'><div class='lab'>WIN RATE</div><div class='val'>—</div></div>",f"<div class='card'><div class='lab'>TODAY P&L</div><div class='val'>{money(pnl.sum())}</div></div>",f"<div class='card'><div class='lab'>OPEN POSITIONS</div><div class='val'>{open_positions}</div></div>"]
    st.markdown("<div class='grid'>"+"".join(cards)+"</div>",unsafe_allow_html=True)
    st.dataframe(today,width="stretch",hide_index=True,height=260) if not today.empty else st.info("No trades recorded today. The paper-trade ledger is ready.")
    st.markdown("<div class='section'>📥 CSV DOWNLOADS — ALWAYS AVAILABLE</div>",unsafe_allow_html=True)
    master=journal_export(trades); today_export=journal_export(today)
    st.download_button("⬇️ Download ALL Daily Trade Details CSV",master.to_csv(index=False).encode("utf-8"),"nse_catalyst_all_trades.csv","text/csv",use_container_width=True,key="download_all_trades")
    st.download_button(f"⬇️ Download TODAY Trade Details CSV ({len(today)})",today_export.to_csv(index=False).encode("utf-8"),f"nse_catalyst_{now.date()}_trades.csv","text/csv",use_container_width=True,key="download_today_trades")
    st.markdown("<div class='section'>🧪 SIGNAL / RESEARCH LEDGER</div>",unsafe_allow_html=True)
    if not signals.empty: st.dataframe(signals.tail(100),width="stretch",hide_index=True,height=260)
    else: st.info("No eligible-signal ledger yet. Signals are recorded only when all mandatory gates pass.")
    st.download_button("⬇️ Download Signal Ledger CSV",signals.to_csv(index=False).encode("utf-8"),"nse_catalyst_signals.csv","text/csv",use_container_width=True,key="download_signals")
    st.caption("Paper trading only • no real Dhan orders are placed • Dhan quotes are used for the master gate/current LTP when configured.")
