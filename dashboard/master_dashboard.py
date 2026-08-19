"""Single combined NSE Catalyst paper-trading dashboard for S1-S5."""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
REFRESH_MS = 15000
CAPITAL_PER_STRATEGY = 250000.0
MAX_TRADES_PER_DAY = 2
DAILY_LOSS_LIMIT = 3000.0
MIN_RISK = 1400.0
MAX_RISK = 1500.0
RR = 1.25
TOTAL_CAPITAL = CAPITAL_PER_STRATEGY * 5

STRATEGIES = {
    "S1": "PDH/PDL Sweep + Open Reclaim",
    "S2": "PDH/PDL Breakout + Retest",
    "S3": "PDL/PDH Sweep + Open Reclaim",
    "S4": "Intraday High/Low Breakout",
    "S5": "Direct PDH/PDL Breakout",
}
QUOTES = [
    "Process first. Profit follows disciplined execution.",
    "Protect capital, wait for alignment, then act.",
    "A good trade is a rule-following trade, not just a winning trade.",
    "Consistency comes from repeating a tested process.",
    "No setup is also a valid decision.",
    "Risk is fixed before the entry; everything else follows.",
]

st.set_page_config(page_title="NSE Catalyst | Master Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=REFRESH_MS, key="master_15s")

st.markdown("""
<style>
.main-title{font-size:2.1rem;font-weight:850;margin:0}.sub{color:#9fb0c7;margin-bottom:18px}
.kpi{border:1px solid #2d405d;border-radius:14px;background:#111a29;padding:14px 16px;min-height:90px}
.kpi small{display:block;color:#91a3ba;font-size:.78rem;font-weight:750;text-transform:uppercase}.kpi b{display:block;font-size:1.45rem;margin-top:5px}
.section{font-size:1.2rem;font-weight:800;margin:22px 0 10px}.good{color:#35d07f}.bad{color:#ff6374}.muted{color:#9fb0c7}
.strategy-card{border:1px solid #2d405d;border-radius:14px;background:#111a29;padding:13px;margin-bottom:8px}.strategy-name{font-weight:800}.strategy-status{font-size:1rem;font-weight:800;margin-top:5px}
.quote{border-left:4px solid #6f8fb8;background:#111a29;padding:14px 18px;border-radius:8px;color:#d9e3f0;font-style:italic}
</style>
""", unsafe_allow_html=True)

def read_json(name):
    p = ROOT / "outputs" / name
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def read_csv(name):
    p = ROOT / "outputs" / name
    try: return pd.read_csv(p)
    except Exception: return pd.DataFrame()

def val(x, default=None):
    try: return float(x)
    except Exception: return default

def money(x):
    x = val(x)
    return f"₹{x:,.0f}" if x is not None else "—"

def pct(x):
    x = val(x)
    return f"{x:+.2f}%" if x is not None else "—"

def age(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=IST)
        return max(0, int((datetime.now(timezone.utc)-d.astimezone(timezone.utc)).total_seconds()))
    except Exception: return None

def kpi(label, value, cls=""):
    return f"<div class='kpi'><small>{label}</small><b class='{cls}'>{value}</b></div>"

def normalize_trades(df):
    if df.empty: return df
    d = df.copy()
    if "strategy" not in d: d["strategy"] = ""
    d["strategy"] = d["strategy"].astype(str).str.upper().replace({"STRATEGY_1":"S1","STRATEGY_2":"S2","STRATEGY_3":"S3","STRATEGY_4":"S4","STRATEGY_5":"S5","OPEN_RETURN":"S1"})
    if "pnl" in d: d["pnl"] = pd.to_numeric(d["pnl"], errors="coerce").fillna(0)
    if "actual_risk" in d: d["actual_risk"] = pd.to_numeric(d["actual_risk"], errors="coerce")
    return d

status = read_json("bot_status.json")
diag = read_json("scanner_diagnostics.json")
state = read_json("paper_engine_state.json")
trades = normalize_trades(read_csv("trades.csv"))
waiting = read_json("waiting_candidates.json")
now = datetime.now(IST)

nifty_change = val(diag.get("nifty500_change_pct"))
ad_ratio = val(diag.get("ad_ratio"))
coverage = int(val(diag.get("nifty500_evaluated", diag.get("nifty500_coverage", 0))) or 0)
ad_complete = coverage >= 500 and bool(diag.get("nifty500_breadth_complete", False))
sector_change = val(diag.get("sector_change_pct"))
sector_alignment = sector_change is not None
buy_aligned = nifty_change is not None and nifty_change > 0 and sector_change is not None and sector_change > 0 and ad_complete and ad_ratio is not None and ad_ratio > 1
sell_aligned = nifty_change is not None and nifty_change < 0 and sector_change is not None and sector_change < 0 and ad_complete and ad_ratio is not None and ad_ratio < 1
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}

st.markdown("<div class='main-title'>📊 NSE Catalyst — Master Dashboard</div>", unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 combined • PAPER TRADING ONLY • live refresh every 15 seconds • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>", unsafe_allow_html=True)

st.markdown("<div class='section'>🎯 Master Market Alignment</div>", unsafe_allow_html=True)
sector_display = pct(sector_change) if sector_change is not None else "UNAVAILABLE"
ad_display = f"{ad_ratio:.2f}" if ad_complete and ad_ratio is not None else "UNAVAILABLE"
bias = "🟢 BUY ALIGNED" if buy_aligned else "🔴 SELL ALIGNED" if sell_aligned else "⚪ NO TRADE"
bias_cls = "good" if buy_aligned else "bad" if sell_aligned else "muted"
st.markdown("<div style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px'>" + "".join([
    kpi("NIFTY 500", pct(nifty_change), "good" if nifty_change is not None and nifty_change > 0 else "bad" if nifty_change is not None and nifty_change < 0 else "muted"),
    kpi("SECTOR ALIGNMENT", sector_display, "good" if sector_change is not None and sector_change > 0 else "bad" if sector_change is not None and sector_change < 0 else "muted"),
    kpi("NIFTY 500 A/D", ad_display, "good" if ad_complete and ad_ratio and ad_ratio > 1 else "bad" if ad_complete and ad_ratio and ad_ratio < 1 else "muted"),
    kpi("A/D COVERAGE", f"{coverage}/500", "good" if coverage >= 500 else "bad"),
    kpi("MASTER BIAS", bias, bias_cls),
]) + "</div>", unsafe_allow_html=True)
if not ad_complete:
    st.warning(f"NIFTY 500 breadth is incomplete ({coverage}/500). A/D is unavailable and trading is BLOCKED until the full 500-stock universe is available.")
if not sector_alignment:
    st.info("Sector alignment is waiting for the live sector feed. No trade is allowed until the sector gate is available and agrees with the direction.")

st.markdown("<div class='section'>💰 Capital & Risk Rules</div>", unsafe_allow_html=True)
st.markdown("<div style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px'>" + "".join([
    kpi("CAPITAL / STRATEGY", money(CAPITAL_PER_STRATEGY)),
    kpi("TOTAL S1–S5 CAPITAL", money(TOTAL_CAPITAL)),
    kpi("RISK / TRADE", "₹1,400–₹1,500"),
    kpi("TARGET", "1.25R"),
    kpi("DAILY LOSS LIMIT", "₹3,000 / strategy"),
]) + "</div>", unsafe_allow_html=True)
st.caption("Position size is calculated from the actual Entry-to-SL distance. If actual risk cannot be kept between ₹1,400 and ₹1,500, the trade is rejected. Maximum 2 trades per strategy per day. Paper orders only.")

st.markdown("<div class='section'>🔥 Live Strategy Board</div>", unsafe_allow_html=True)
summary=[]
for s,name in STRATEGIES.items():
    sd = {"Strategy":s,"Name":name,"Trades Today":0,"Daily P&L":0.0,"Status":"WAITING"}
    if not trades.empty:
        td=trades[trades["strategy"]==s].copy()
        if not td.empty:
            today=td
            if "entry_time" in td:
                dates=pd.to_datetime(td["entry_time"],errors="coerce")
                today=td[dates.dt.date==now.date()]
            sd["Trades Today"]=len(today)
            sd["Daily P&L"]=float(today["pnl"].sum()) if "pnl" in today else 0.0
    if sd["Trades Today"]>=MAX_TRADES_PER_DAY or sd["Daily P&L"]<=-DAILY_LOSS_LIMIT: sd["Status"]="🔒 LOCKED"
    elif positions: sd["Status"]="🟢 ACTIVE"
    elif buy_aligned or sell_aligned: sd["Status"]="🟡 MARKET ALIGNED"
    else: sd["Status"]="⚪ WAITING"
    summary.append(sd)
summary_df=pd.DataFrame(summary)
cols=st.columns(5)
for col,row in zip(cols,summary):
    with col:
        st.markdown(f"<div class='strategy-card'><div class='strategy-name'>{row['Strategy']} • {row['Name']}</div><div class='strategy-status'>{row['Status']}</div><div class='muted'>Trades: {row['Trades Today']}/2</div><div class='muted'>Daily P&L: {money(row['Daily P&L'])}</div></div>",unsafe_allow_html=True)

st.markdown("<div class='section'>💼 Current Paper Trades</div>", unsafe_allow_html=True)
if positions:
    rows=[]
    for symbol,p in positions.items():
        rows.append({"Strategy":p.get("strategy","—"),"Stock":symbol,"Side":p.get("signal","—"),"Entry":p.get("entry"),"SL":p.get("stop_loss"),"Target":p.get("target"),"Qty":p.get("quantity"),"Risk":p.get("actual_risk"),"Entry Time":p.get("entry_time","—")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No open paper trades. The engine is waiting for a complete market-alignment + OHLC/PDH/PDL setup.")

st.markdown("<div class='section'>📈 Live & Historical Analysis</div>", unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:
    chart=trades.copy()
    chart["pnl"]=pd.to_numeric(chart["pnl"],errors="coerce").fillna(0)
    chart["strategy"]=chart["strategy"].replace({"STRATEGY_1":"S1","STRATEGY_2":"S2","STRATEGY_3":"S3","STRATEGY_4":"S4","STRATEGY_5":"S5"})
    perf=chart.groupby("strategy")["pnl"].agg(["sum","count"]).reindex(list(STRATEGIES.keys())).fillna(0).reset_index()
    perf["wins"]=perf["strategy"].map(chart.assign(win=chart["pnl"]>0).groupby("strategy")["win"].sum()).fillna(0)
    perf["win_rate"]=perf["wins"].div(perf["count"].replace(0,pd.NA)).mul(100).fillna(0)
    c1,c2=st.columns(2)
    with c1:
        fig=px.bar(perf,x="strategy",y="sum",title="Net P&L by Strategy",text_auto=True)
        fig.update_layout(margin=dict(l=10,r=10,t=45,b=10),height=330)
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        fig=px.bar(perf,x="strategy",y="win_rate",title="Win Rate %",text_auto='.1f')
        fig.update_layout(margin=dict(l=10,r=10,t=45,b=10),height=330,yaxis_title="%")
        st.plotly_chart(fig,use_container_width=True)
    c3,c4=st.columns(2)
    with c3:
        fig=px.bar(perf,x="strategy",y="count",title="Trades by Strategy",text_auto=True)
        fig.update_layout(margin=dict(l=10,r=10,t=45,b=10),height=300)
        st.plotly_chart(fig,use_container_width=True)
    with c4:
        win_loss=perf[["strategy","wins"]].copy(); win_loss["losses"]=perf["count"]-perf["wins"]
        wl=win_loss.melt(id_vars="strategy",var_name="Outcome",value_name="Trades")
        fig=px.bar(wl,x="strategy",y="Trades",color="Outcome",barmode="stack",title="Wins vs Losses")
        fig.update_layout(margin=dict(l=10,r=10,t=45,b=10),height=300)
        st.plotly_chart(fig,use_container_width=True)
    # Cumulative P&L line
    seq=chart.sort_values("entry_time") if "entry_time" in chart else chart
    if not seq.empty:
        seq["cum_pnl"]=seq.groupby("strategy")["pnl"].cumsum()
        fig=px.line(seq,x="entry_time" if "entry_time" in seq else seq.index,y="cum_pnl",color="strategy",markers=True,title="Cumulative P&L")
        fig.update_layout(margin=dict(l=10,r=10,t=45,b=10),height=360)
        st.plotly_chart(fig,use_container_width=True)
    # Pie chart only as a compact outcome view, not the main analysis.
    pie=perf[["strategy","wins"]].copy();pie["losses"]=perf["count"]-perf["wins"]
    pie_total=pie[["wins","losses"]].sum()
    if pie_total.sum()>0:
        fig=px.pie(values=pie_total.values,names=pie_total.index,title="Overall Trade Outcomes")
        fig.update_layout(height=300,margin=dict(l=10,r=10,t=45,b=10))
        st.plotly_chart(fig,use_container_width=True)
else:
    st.info("Charts will populate automatically as paper trades are recorded. No fake performance values are shown before real trade history exists.")

st.markdown("<div class='section'>🏆 Strategy Comparison</div>", unsafe_allow_html=True)
if not trades.empty and "pnl" in trades:
    perf2=summary_df[["Strategy","Daily P&L","Trades Today"]].copy()
    st.dataframe(perf2,use_container_width=True,hide_index=True)
else:
    st.caption("Historical probability, win rate, profit factor, drawdown and ranking will be calculated from the master journal once sufficient paper-trade history exists.")

st.markdown("<div class='section'>📋 Master Paper-Trading Journal</div>", unsafe_allow_html=True)
st.caption("One consolidated journal for S1–S5. The export ends with a DAILY_QUOTE row that changes by date.")
try:
    from journal.master_journal import build_journal
    journal_path=build_journal()
    journal_df=pd.read_csv(journal_path)
    st.dataframe(journal_df.tail(25),use_container_width=True,hide_index=True)
    st.download_button("⬇️ Download Master Journal CSV", data=journal_path.read_bytes(), file_name="strategy_journal_master.csv", mime="text/csv")
except Exception as e:
    st.warning(f"Master journal will be available after the first successful journal build: {type(e).__name__}")

quote=QUOTES[now.date().toordinal()%len(QUOTES)]
st.markdown(f"<div class='quote'>🧠 Daily Trading Quote — “{quote}”</div>",unsafe_allow_html=True)
st.caption("Paper trading only • No live orders • Dashboard refresh: 15 seconds • Dhan web/API can be connected later as the live data source.")
