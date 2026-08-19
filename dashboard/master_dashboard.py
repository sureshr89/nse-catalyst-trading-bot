"""NSE Catalyst - single combined paper-trading master dashboard for S1-S5."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
REFRESH_SECONDS = 15
CAPITAL_PER_TRADE = 250000.0
MAX_TRADES_PER_STRATEGY_DAY = 1
MAX_OPEN_TRADES_PER_STRATEGY = 1
DAILY_LOSS_LIMIT = 1500.0
MIN_RISK = 1400.0
MAX_RISK = 1500.0
RR = 1.25

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
    "Wait for alignment. Trade only the setup you can explain.",
]

st.set_page_config(page_title="NSE Catalyst | Master Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="nse_catalyst_master_15s")

st.markdown("""
<style>
.block-container{padding-top:1.1rem;padding-bottom:2rem;max-width:1500px}
.title{font-size:2.15rem;font-weight:900;line-height:1.1;margin-bottom:4px}
.subtitle{color:#9fb0c7;font-size:.92rem;margin-bottom:16px}
.section{font-size:1.22rem;font-weight:850;margin:22px 0 10px}
.card{border:1px solid #2c3e5b;border-radius:14px;background:#111a29;padding:13px 15px;min-height:88px}
.card small{display:block;color:#8fa3bd;font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
.card b{display:block;font-size:1.35rem;margin-top:5px}
.good{color:#36d982}.bad{color:#ff6476}.warn{color:#ffd166}.muted{color:#9fb0c7}
.trade-card{border:1px solid #334b6c;border-radius:14px;background:#101a2a;padding:12px;margin-bottom:8px}
.trade-card .head{font-size:1rem;font-weight:850}.trade-card .line{color:#a7b8cd;font-size:.82rem;margin-top:4px}
.quote{border-left:4px solid #6f8fb8;background:#111a29;padding:14px 18px;border-radius:9px;color:#d9e3f0;font-style:italic}
</style>
""", unsafe_allow_html=True)

def read_json(name):
    try:
        return json.loads((ROOT / "outputs" / name).read_text(encoding="utf-8"))
    except Exception:
        return {}

def read_csv(name):
    try:
        return pd.read_csv(ROOT / "outputs" / name)
    except Exception:
        return pd.DataFrame()

def num(x, default=None):
    try: return float(x)
    except Exception: return default

def money(x):
    x = num(x)
    return f"₹{x:,.0f}" if x is not None else "—"

def pct(x):
    x = num(x)
    return f"{x:+.2f}%" if x is not None else "—"

def normalize_trades(df):
    if df.empty: return df
    d = df.copy()
    if "strategy" not in d: d["strategy"] = ""
    d["strategy"] = d["strategy"].astype(str).str.upper().replace({
        "STRATEGY_1":"S1","STRATEGY_2":"S2","STRATEGY_3":"S3",
        "STRATEGY_4":"S4","STRATEGY_5":"S5","OPEN_RETURN":"S1"
    })
    if "pnl" not in d: d["pnl"] = 0.0
    d["pnl"] = pd.to_numeric(d["pnl"], errors="coerce").fillna(0.0)
    return d

def today_rows(df, now):
    if df.empty or "entry_time" not in df: return df
    dt = pd.to_datetime(df["entry_time"], errors="coerce")
    return df[dt.dt.date == now.date()].copy()

def kpi(label, value, cls="muted"):
    return f"<div class='card'><small>{label}</small><b class='{cls}'>{value}</b></div>"

def daily_quote(now):
    return QUOTES[now.toordinal() % len(QUOTES)]

def master_journal(df, now):
    cols = ["date","strategy","stock","side","entry_time","entry","sl","target","quantity","actual_risk","exit_time","exit","pnl","outcome","notes"]
    if df.empty:
        out = pd.DataFrame(columns=cols)
    else:
        out = df.copy()
        aliases = {"symbol":"stock","signal":"side","stop_loss":"sl","take_profit":"target","exit_price":"exit","closed_at":"exit_time","status":"outcome"}
        for src,dst in aliases.items():
            if dst not in out.columns and src in out.columns: out[dst] = out[src]
        if "date" not in out.columns: out["date"] = now.date().isoformat()
        for c in cols:
            if c not in out.columns: out[c] = ""
        out = out[cols]
    quote = {c:"" for c in cols}
    quote["date"] = now.date().isoformat()
    quote["strategy"] = "DAILY_QUOTE"
    quote["notes"] = daily_quote(now)
    return pd.concat([out, pd.DataFrame([quote])], ignore_index=True)

now = datetime.now(IST)
diag = read_json("scanner_diagnostics.json")
state = read_json("paper_engine_state.json")
trades = normalize_trades(read_csv("trades.csv"))
today = today_rows(trades, now)
positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
if not isinstance(positions, dict): positions = {}

nifty = num(diag.get("nifty500_change_pct"))
sector = num(diag.get("sector_change_pct"))
ad = num(diag.get("ad_ratio"))
coverage = int(num(diag.get("nifty500_evaluated", diag.get("nifty500_coverage", 0))) or 0)
ad_complete = coverage >= 500 and bool(diag.get("nifty500_breadth_complete", False))
buy_aligned = nifty is not None and nifty > 0 and sector is not None and sector > 0 and ad_complete and ad is not None and ad > 1
sell_aligned = nifty is not None and nifty < 0 and sector is not None and sector < 0 and ad_complete and ad is not None and ad < 1

st.markdown("<div class='title'>📊 NSE Catalyst — Master Dashboard</div>", unsafe_allow_html=True)
st.markdown(f"<div class='subtitle'>NIFTY 500 • S1–S5 combined • PAPER TRADING ONLY • refresh every {REFRESH_SECONDS} seconds • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>", unsafe_allow_html=True)

st.markdown("<div class='section'>🎯 Master Market Alignment</div>", unsafe_allow_html=True)
ad_text = f"{ad:.2f}" if ad_complete and ad is not None else "UNAVAILABLE"
bias = "🟢 BUY ALIGNED" if buy_aligned else "🔴 SELL ALIGNED" if sell_aligned else "⚪ NO TRADE"
bias_cls = "good" if buy_aligned else "bad" if sell_aligned else "muted"
cards = [
    kpi("NIFTY 500", pct(nifty), "good" if nifty is not None and nifty > 0 else "bad" if nifty is not None and nifty < 0 else "muted"),
    kpi("SECTOR ALIGNMENT", pct(sector) if sector is not None else "UNAVAILABLE", "good" if sector is not None and sector > 0 else "bad" if sector is not None and sector < 0 else "muted"),
    kpi("NIFTY 500 A/D", ad_text, "good" if ad_complete and ad is not None and ad > 1 else "bad" if ad_complete and ad is not None and ad < 1 else "muted"),
    kpi("A/D COVERAGE", f"{coverage}/500", "good" if ad_complete else "bad"),
    kpi("MASTER BIAS", bias, bias_cls),
]
st.markdown("<div style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
if not ad_complete:
    st.error(f"🚫 TRADING BLOCKED — NIFTY 500 A/D is incomplete ({coverage}/500). Full 500-stock breadth is mandatory.")
if sector is None:
    st.warning("🚫 TRADING BLOCKED — sector alignment is unavailable.")

st.markdown("<div class='section'>🔒 Fixed Paper-Trading Rules</div>", unsafe_allow_html=True)
rules = [
    kpi("CAPITAL / TRADE", "₹2,50,000"),
    kpi("RISK / TRADE", "₹1,400–₹1,500"),
    kpi("TARGET", "1.25R"),
    kpi("MAX TRADES / STRATEGY", "1 / day"),
    kpi("MAX DAILY LOSS", "₹1,500 / strategy"),
]
st.markdown("<div style='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px'>" + "".join(rules) + "</div>", unsafe_allow_html=True)
st.caption("Position size is derived from actual Entry→SL distance. If actual risk is outside ₹1,400–₹1,500, the trade is rejected. Only one open trade per strategy at a time. Paper trading only; no real orders.")

st.markdown("<div class='section'>🔥 All 5 Strategies — One-Glance Board</div>", unsafe_allow_html=True)
summary = []
for s,name in STRATEGIES.items():
    td = today[today["strategy"] == s] if not today.empty else pd.DataFrame()
    pnl = float(td["pnl"].sum()) if not td.empty else 0.0
    wins = int((td["pnl"] > 0).sum()) if not td.empty else 0
    losses = int((td["pnl"] < 0).sum()) if not td.empty else 0
    open_count = sum(1 for p in positions.values() if isinstance(p, dict) and str(p.get("strategy", "")).upper().replace("STRATEGY_", "S") == s)
    if len(td) >= MAX_TRADES_PER_STRATEGY_DAY or pnl <= -DAILY_LOSS_LIMIT:
        status = "🔒 LOCKED"
        status_cls = "bad"
    elif open_count >= MAX_OPEN_TRADES_PER_STRATEGY:
        status = "🟢 ACTIVE"
        status_cls = "good"
    elif buy_aligned or sell_aligned:
        status = "🟡 ALIGNED"
        status_cls = "warn"
    else:
        status = "⚪ WAITING"
        status_cls = "muted"
    summary.append({"Strategy":s,"Setup":name,"Status":status,"Trades":len(td),"Wins":wins,"Losses":losses,"Daily P&L":pnl})
cols = st.columns(5)
for col,row in zip(cols,summary):
    with col:
        st.markdown(f"<div class='trade-card'><div class='head'>{row['Strategy']} • <span class='{status_cls}'>{row['Status']}</span></div><div class='line'>{row['Setup']}</div><div class='line'>Trades {row['Trades']}/1 • Wins {row['Wins']} • Losses {row['Losses']}</div><div class='line'>Daily P&L <b>{money(row['Daily P&L'])}</b></div></div>", unsafe_allow_html=True)

st.markdown("<div class='section'>💼 Current Paper Trades — All Strategies</div>", unsafe_allow_html=True)
if positions:
    live=[]
    for symbol,p in positions.items():
        if not isinstance(p, dict): continue
        live.append({
            "Strategy":p.get("strategy","—"), "Stock":symbol, "Side":p.get("signal",p.get("side","—")),
            "Entry":p.get("entry"), "LTP":p.get("ltp",p.get("current_price")), "SL":p.get("stop_loss"),
            "Target":p.get("target",p.get("take_profit")), "Qty":p.get("quantity"), "Risk":p.get("actual_risk"),
            "P&L":p.get("pnl"), "Entry Time":p.get("entry_time","—")
        })
    if live: st.dataframe(pd.DataFrame(live), use_container_width=True, hide_index=True)
else:
    st.info("No open paper trades — waiting for complete alignment and an exact OHLC/PDH/PDL setup.")

st.markdown("<div class='section'>📈 Live / Historical Charts</div>", unsafe_allow_html=True)
if trades.empty:
    st.info("Charts will populate from real paper-trade history. No artificial performance numbers are shown.")
else:
    t = trades.copy()
    t["pnl"] = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
    t["strategy"] = t["strategy"].astype(str).str.upper().replace({f"STRATEGY_{i}":f"S{i}" for i in range(1,6)})
    perf = t.groupby("strategy")["pnl"].agg(total_pnl="sum", trades="count").reindex(list(STRATEGIES)).fillna(0).reset_index()
    perf["wins"] = perf["strategy"].map(t.assign(win=t["pnl"]>0).groupby("strategy")["win"].sum()).fillna(0)
    perf["losses"] = perf["strategy"].map(t.assign(loss=t["pnl"]<0).groupby("strategy")["loss"].sum()).fillna(0)
    perf["win_rate"] = (perf["wins"] / perf["trades"].replace(0,pd.NA) * 100).fillna(0)
    gross_w = t[t["pnl"]>0].groupby("strategy")["pnl"].sum()
    gross_l = -t[t["pnl"]<0].groupby("strategy")["pnl"].sum()
    perf["gross_profit"] = perf["strategy"].map(gross_w).fillna(0)
    perf["gross_loss"] = perf["strategy"].map(gross_l).fillna(0)
    perf["profit_factor"] = (perf["gross_profit"] / perf["gross_loss"].replace(0,pd.NA)).fillna(0)

    a,b = st.columns(2)
    with a:
        fig=px.bar(perf,x="strategy",y="total_pnl",text_auto=True,title="💰 Net P&L by Strategy")
        fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    with b:
        fig=px.bar(perf,x="strategy",y="win_rate",text_auto='.1f',title="🎯 Win Rate % by Strategy")
        fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10),yaxis_title="%"); st.plotly_chart(fig,use_container_width=True)
    a,b = st.columns(2)
    with a:
        fig=px.bar(perf,x="strategy",y="profit_factor",text_auto='.2f',title="📊 Profit Factor by Strategy")
        fig.update_layout(height=300,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    with b:
        wl=perf[["strategy","wins","losses"]].melt(id_vars="strategy",var_name="Outcome",value_name="Trades")
        fig=px.bar(wl,x="strategy",y="Trades",color="Outcome",barmode="stack",title="🏆 Wins vs Losses")
        fig.update_layout(height=300,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    if "entry_time" in t:
        t["entry_time"] = pd.to_datetime(t["entry_time"], errors="coerce")
        q=t.dropna(subset=["entry_time"]).sort_values("entry_time")
        if not q.empty:
            q["cum_pnl"] = q.groupby("strategy")["pnl"].cumsum()
            fig=px.line(q,x="entry_time",y="cum_pnl",color="strategy",markers=True,title="📈 Cumulative P&L — S1 to S5")
            fig.update_layout(height=380,margin=dict(l=10,r=10,t=45,b=10),yaxis_title="₹"); st.plotly_chart(fig,use_container_width=True)
    outcome=perf[["wins","losses"]].sum()
    if outcome.sum()>0:
        fig=px.pie(values=outcome.values,names=["Wins","Losses"],hole=.45,title="🥧 Overall Trade Outcomes")
        fig.update_layout(height=320,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)

st.markdown("<div class='section'>🏆 Overall Strategy Performance — S1 to S5</div>", unsafe_allow_html=True)
if trades.empty:
    st.info("No historical paper trades yet. Overall statistics will appear after actual paper trades are recorded.")
else:
    rows=[]
    for s,name in STRATEGIES.items():
        td=trades[trades["strategy"]==s].copy()
        n=len(td)
        wins=int((td["pnl"]>0).sum()) if n else 0
        losses=int((td["pnl"]<0).sum()) if n else 0
        breakeven=int((td["pnl"]==0).sum()) if n else 0
        gross_profit=float(td.loc[td["pnl"]>0,"pnl"].sum()) if n else 0.0
        gross_loss=float(-td.loc[td["pnl"]<0,"pnl"].sum()) if n else 0.0
        net=float(td["pnl"].sum()) if n else 0.0
        avg_win=float(td.loc[td["pnl"]>0,"pnl"].mean()) if wins else 0.0
        avg_loss=float(td.loc[td["pnl"]<0,"pnl"].mean()) if losses else 0.0
        best=float(td["pnl"].max()) if n else 0.0
        worst=float(td["pnl"].min()) if n else 0.0
        rows.append({
            "Strategy":s,
            "Setup":name,
            "Total Trades":n,
            "Wins":wins,
            "Losses":losses,
            "Breakeven":breakeven,
            "Win Rate %":round(wins/n*100,1) if n else 0.0,
            "Gross Profit":round(gross_profit,2),
            "Gross Loss":round(gross_loss,2),
            "Net P&L":round(net,2),
            "Avg Win":round(avg_win,2),
            "Avg Loss":round(avg_loss,2),
            "Best Trade":round(best,2),
            "Worst Trade":round(worst,2),
            "Profit Factor":round(gross_profit/gross_loss,2) if gross_loss else None,
        })
    overall_df=pd.DataFrame(rows)
    st.dataframe(overall_df,use_container_width=True,hide_index=True)
    best_strategy=overall_df.loc[overall_df["Net P&L"].idxmax(),"Strategy"] if not overall_df.empty else "—"
    total_net=float(overall_df["Net P&L"].sum()) if not overall_df.empty else 0.0
    total_wins=int(overall_df["Wins"].sum()) if not overall_df.empty else 0
    total_losses=int(overall_df["Losses"].sum()) if not overall_df.empty else 0
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Total Wins — All Strategies", total_wins)
    with c2: st.metric("Total Losses — All Strategies", total_losses)
    with c3: st.metric("Combined Net P&L", money(total_net))
    with c4: st.metric("Best Strategy by Net P&L", best_strategy)
    st.caption("Overall figures use only recorded paper trades. No success probability is invented from a small sample.")

st.markdown("<div class='section'>📒 Master Strategy Journal — S1 to S5</div>", unsafe_allow_html=True)
journal=master_journal(trades,now)
st.dataframe(journal.tail(100),use_container_width=True,hide_index=True)
st.download_button("⬇️ DOWNLOAD MASTER JOURNAL CSV", data=journal.to_csv(index=False).encode("utf-8-sig"), file_name="strategy_journal_master.csv", mime="text/csv", use_container_width=True)
st.caption("One master CSV only. All five strategies share the same journal. The final row is today's fresh daily quote.")

st.markdown("<div class='section'>🧠 Daily Trading Quote</div>", unsafe_allow_html=True)
st.markdown(f"<div class='quote'>“{daily_quote(now)}”</div>", unsafe_allow_html=True)

with st.expander("⚙️ System / Data Status", expanded=False):
    st.json({
        "mode":"PAPER_ONLY","refresh_seconds":REFRESH_SECONDS,"capital_per_trade":CAPITAL_PER_TRADE,
        "max_trades_per_strategy_day":MAX_TRADES_PER_STRATEGY_DAY,"max_open_trades_per_strategy":MAX_OPEN_TRADES_PER_STRATEGY,
        "daily_loss_limit_per_strategy":DAILY_LOSS_LIMIT,"risk_range":"₹1,400–₹1,500","target_rr":RR,
        "nifty500_change":nifty,"sector_change":sector,"ad_ratio":ad if ad_complete else None,"ad_coverage":f"{coverage}/500",
        "buy_alignment":buy_aligned,"sell_alignment":sell_aligned,"open_positions":len(positions)
    })

st.caption("NSE Catalyst • single combined dashboard • S1–S5 • paper trading only • live API can be connected later.")
