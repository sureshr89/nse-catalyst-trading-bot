"""Read-only visual strategy research dashboard."""
from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
SIGNALS_FILE = PROJECT_ROOT / "outputs" / "signals.csv"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_engine_state.json"

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}
.analysis-title {font-size:2rem; font-weight:700; margin-bottom:.1rem;}
.analysis-subtitle {opacity:.72; margin-bottom:1rem;}
.section-title {font-size:1.1rem; font-weight:650; margin-top:1.35rem; margin-bottom:.55rem;}
[data-testid="stMetric"] {padding:.65rem .8rem; border:1px solid rgba(128,128,128,.18); border-radius:10px;}
</style>
""", unsafe_allow_html=True)


def load_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def numeric(df, column, default=0.0):
    if column not in df.columns:
        df[column] = default
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(default)


def prepare(df):
    df = df.copy()
    if df.empty:
        return df
    for col in ["entry", "stop_loss", "target", "quantity", "risk", "reward", "rr", "pnl", "actual_risk", "position_value", "risk_reward"]:
        numeric(df, col)
    if "risk" in df.columns and "entry" in df.columns and "stop_loss" in df.columns and "quantity" in df.columns:
        mask = df["risk"] <= 0
        df.loc[mask, "risk"] = (df.loc[mask, "entry"] - df.loc[mask, "stop_loss"]).abs() * df.loc[mask, "quantity"]
    if "reward" in df.columns:
        mask = df["reward"] <= 0
        df.loc[mask, "reward"] = (df.loc[mask, "target"] - df.loc[mask, "entry"]).abs() * df.loc[mask, "quantity"]
    mask = df["risk"] > 0
    df.loc[mask, "rr"] = df.loc[mask, "reward"] / df.loc[mask, "risk"]
    df["Result"] = df["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    return df


def stats(df):
    if df.empty:
        return {"Trades":0,"Wins":0,"Losses":0,"Flat":0,"Win Rate %":0.0,"P&L":0.0,"Avg P&L":0.0,"Avg Win":0.0,"Avg Loss":0.0,"Expectancy":0.0,"Profit Factor":0.0,"Avg Risk":0.0,"Avg R:R":0.0}
    pnl = df["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gp = float(wins.sum())
    gl = abs(float(losses.sum()))
    return {
        "Trades": len(df), "Wins": int((pnl > 0).sum()), "Losses": int((pnl < 0).sum()), "Flat": int((pnl == 0).sum()),
        "Win Rate %": round(float((pnl > 0).mean() * 100), 2), "P&L": round(float(pnl.sum()), 2),
        "Avg P&L": round(float(pnl.mean()), 2), "Avg Win": round(float(wins.mean()), 2) if not wins.empty else 0.0,
        "Avg Loss": round(float(losses.mean()), 2) if not losses.empty else 0.0,
        "Expectancy": round(float(pnl.mean()), 2), "Profit Factor": round(gp / gl, 3) if gl else 0.0,
        "Avg Risk": round(float(df["risk"].mean()), 2), "Avg R:R": round(float(df["rr"].mean()), 3),
    }


def group_stats(df, column):
    if df.empty or column not in df.columns:
        return pd.DataFrame()
    rows = []
    for value, group in df.groupby(column, dropna=False):
        row = stats(group)
        row[column] = str(value) if pd.notna(value) and str(value) else "UNKNOWN"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("P&L", ascending=False) if rows else pd.DataFrame()


def make_pie(df, column, title):
    if df.empty or column not in df.columns:
        return
    counts = df[column].fillna("UNKNOWN").astype(str).value_counts().reset_index()
    counts.columns = [column, "Count"]
    fig = px.pie(counts, names=column, values="Count", hole=.45, title=title)
    fig.update_layout(height=340, margin=dict(l=10,r=10,t=55,b=10), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


trades = prepare(load_csv(TRADES_FILE))
signals = load_csv(SIGNALS_FILE)
state = load_json(STATE_FILE)

if not trades.empty and "status" in trades.columns:
    status_col = trades["status"].astype(str).str.upper()
    actual = trades[status_col == "CLOSED"].copy()
    missed = trades[status_col.isin(["MISSED_CAPITAL_OPEN", "MISSED_CAPITAL_CLOSED"])].copy()
else:
    actual = pd.DataFrame()
    missed = pd.DataFrame()

actual = prepare(actual)
missed = prepare(missed)
missed_closed = missed[missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_CLOSED"].copy() if not missed.empty else pd.DataFrame()

st.markdown('<div class="analysis-title">📊 Strategy Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="analysis-subtitle">NIFTY 100 Gap-Failure + Open-Reclaim • read-only research • actual trades and capital-missed opportunities are analysed separately</div>', unsafe_allow_html=True)

# ------------------------------ TOP KPIs -------------------------------
a = stats(actual)
m = stats(missed_closed)
qualified = len(actual) + len(missed_closed)
combined_pnl = a["P&L"] + m["P&L"]

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Actual Trades", a["Trades"])
c2.metric("Actual Win Rate", f'{a["Win Rate %"]:.1f}%')
c3.metric("Actual P&L", f'₹{a["P&L"]:,.2f}')
c4.metric("Missed Capital", len(missed))
c5.metric("Missed Hyp. P&L", f'₹{m["P&L"]:,.2f}')
c6.metric("Qualified Outcomes", qualified)

# -------------------------- PERFORMANCE CURVES -------------------------
st.markdown('<div class="section-title">Performance & P&L</div>', unsafe_allow_html=True)
if actual.empty:
    st.info("No closed actual trades yet. Performance charts will populate automatically after trades close.")
else:
    curve = actual.copy()
    time_col = next((x for x in ["exit_time", "entry_time"] if x in curve.columns), None)
    if time_col:
        curve["_time"] = pd.to_datetime(curve[time_col], errors="coerce")
        curve = curve.sort_values("_time", na_position="last")
    curve["Trade #"] = range(1, len(curve)+1)
    curve["Cumulative P&L"] = curve["pnl"].cumsum()
    curve["Drawdown"] = curve["Cumulative P&L"] - curve["Cumulative P&L"].cummax()
    left, right = st.columns(2)
    with left:
        fig = px.line(curve, x="Trade #", y="Cumulative P&L", markers=True, title="Cumulative Actual P&L")
        fig.update_layout(height=360, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.bar(curve, x="Trade #", y="pnl", title="Individual Trade P&L Spikes")
        fig.update_layout(height=360, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
        st.plotly_chart(fig, use_container_width=True)
    fig = px.line(curve, x="Trade #", y="Drawdown", markers=True, title="Drawdown")
    fig.update_layout(height=320, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------- OUTCOMES --------------------------------
st.markdown('<div class="section-title">Outcome Analysis</div>', unsafe_allow_html=True)
if actual.empty:
    st.info("No actual trade outcomes available yet.")
else:
    left, right = st.columns(2)
    with left:
        make_pie(actual.assign(Outcome=actual["Result"]), "Outcome", "Actual Win / Loss / Flat")
    with right:
        make_pie(actual, "exit_reason", "Actual Exit Reasons")

    outcome = pd.DataFrame([{
        "Trades": a["Trades"], "Wins": a["Wins"], "Losses": a["Losses"], "Flat": a["Flat"],
        "Win Rate %": a["Win Rate %"], "Average P&L": a["Avg P&L"], "Average Win": a["Avg Win"],
        "Average Loss": a["Avg Loss"], "Expectancy": a["Expectancy"], "Profit Factor": a["Profit Factor"],
        "Average Risk": a["Avg Risk"], "Average R:R": a["Avg R:R"],
    }])
    st.dataframe(outcome, use_container_width=True, hide_index=True)

# ------------------------- SIDE / EXIT / STOCK -------------------------
st.markdown('<div class="section-title">Where the Strategy Works</div>', unsafe_allow_html=True)
if not actual.empty:
    left, right = st.columns(2)
    with left:
        side = group_stats(actual, "signal")
        if not side.empty:
            fig = px.bar(side, x="signal", y="P&L", text="Trades", title="P&L by BUY / SELL")
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        exit_stats = group_stats(actual, "exit_reason")
        if not exit_stats.empty:
            fig = px.bar(exit_stats, x="exit_reason", y="P&L", text="Trades", title="P&L by Exit Reason")
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
            st.plotly_chart(fig, use_container_width=True)

    stock_stats = group_stats(actual, "symbol")
    if not stock_stats.empty:
        st.subheader("Stock-Level Performance")
        fig = px.bar(stock_stats.head(20), x="symbol", y="P&L", text="Trades", title="Top 20 Stocks by Actual P&L")
        fig.update_layout(height=390, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(stock_stats, use_container_width=True, hide_index=True)

# ------------------------------- RISK ---------------------------------
st.markdown('<div class="section-title">Risk & R:R Analysis</div>', unsafe_allow_html=True)
if not actual.empty:
    risk_df = actual.copy()
    left, right = st.columns(2)
    with left:
        fig = px.scatter(risk_df, x="risk", y="pnl", size="quantity" if "quantity" in risk_df else None, hover_name="symbol", hover_data=["signal","rr"], title="Risk vs Actual P&L")
        fig.update_layout(height=370, margin=dict(l=10,r=10,t=55,b=10), xaxis_title="Risk (₹)", yaxis_title="P&L (₹)")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.scatter(risk_df, x="rr", y="pnl", hover_name="symbol", hover_data=["signal","risk"], title="R:R vs Actual P&L")
        fig.update_layout(height=370, margin=dict(l=10,r=10,t=55,b=10), xaxis_title="R:R", yaxis_title="P&L (₹)")
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------ TIMING --------------------------------
st.markdown('<div class="section-title">Signal & Trade Timing</div>', unsafe_allow_html=True)
if signals.empty:
    st.info("No scanner signals available for timing analysis yet.")
else:
    sig = signals.copy()
    if "timestamp" in sig.columns:
        sig["_time"] = pd.to_datetime(sig["timestamp"], errors="coerce")
        sig = sig[sig["_time"].notna()].copy()
        if not sig.empty:
            sig["Minute"] = sig["_time"].dt.strftime("%H:%M")
            counts = sig.groupby("Minute").size().reset_index(name="Signals")
            fig = px.bar(counts, x="Minute", y="Signals", title="Scanner Signal Spikes by Time")
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=55,b=10), xaxis_title="IST")
            st.plotly_chart(fig, use_container_width=True)

    if "approved" in sig.columns:
        approved = sig["approved"].astype(str).str.upper().isin(["TRUE","1","YES"])
        left, right = st.columns(2)
        with left:
            fig = px.pie(pd.DataFrame({"Status":["Approved","Rejected"],"Count":[int(approved.sum()),int((~approved).sum())]}), names="Status", values="Count", hole=.45, title="Signal Approval")
            fig.update_layout(height=330, margin=dict(l=10,r=10,t=55,b=10))
            st.plotly_chart(fig, use_container_width=True)
        with right:
            if "reason" in sig.columns:
                reason_counts = sig["reason"].fillna("No reason").astype(str).value_counts().head(12).reset_index()
                reason_counts.columns = ["Reason","Count"]
                fig = px.bar(reason_counts, x="Count", y="Reason", orientation="h", title="Top Signal Reasons")
                fig.update_layout(height=330, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="")
                st.plotly_chart(fig, use_container_width=True)

# ------------------------ MARKET ALIGNMENT -----------------------------
st.markdown('<div class="section-title">Market / Sector / Setup Analysis</div>', unsafe_allow_html=True)
if not actual.empty:
    for col in ["nifty100_direction", "sector_direction", "stock_today_direction", "previous_day_direction", "setup_type"]:
        if col in actual.columns and actual[col].notna().any():
            table = group_stats(actual, col)
            if not table.empty:
                fig = px.bar(table, x=col, y="P&L", text="Trades", title=f"Actual P&L by {col.replace('_',' ').title()}")
                fig.update_layout(height=330, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
                st.plotly_chart(fig, use_container_width=True)

# --------------------- ACTUAL VS MISSED CAPITAL ------------------------
st.markdown('<div class="section-title">Strategy Capability: Actual vs Capital-Missed</div>', unsafe_allow_html=True)
comparison = pd.DataFrame([
    {"Category":"Actual trades", **a},
    {"Category":"Capital-missed resolved", **m},
])
st.dataframe(comparison, use_container_width=True, hide_index=True)
if not missed.empty:
    left, right = st.columns(2)
    with left:
        resolved = missed_closed.copy()
        if not resolved.empty:
            fig = px.bar(pd.DataFrame({"Category":["Actual","Missed due to capital"],"P&L":[a["P&L"],m["P&L"]]}), x="Category", y="P&L", title="Realized vs Hypothetical P&L")
            fig.update_layout(height=340, margin=dict(l=10,r=10,t=55,b=10), yaxis_title="₹")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        make_pie(pd.DataFrame({"Category":["Actual","Missed due to capital"],"Count":[len(actual),len(missed_closed)]}), "Category", "Actual vs Resolved Capital-Missed")
    st.caption("Capital-missed results are hypothetical. They never change actual trading P&L.")

# ----------------------------- TABLES ----------------------------------
st.markdown('<div class="section-title">Detailed Research Data</div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["Actual Trades", "Capital-Missed", "Scanner Signals"])
with tab1:
    if actual.empty:
        st.info("No actual trades yet.")
    else:
        preferred = ["trade_id","symbol","signal","entry_time","entry","stop_loss","target","quantity","risk","reward","rr","exit_time","exit_price","exit_reason","pnl","nifty100_direction","sector","sector_direction","stock_today_direction","previous_day_direction","setup_type","status"]
        cols = [c for c in preferred if c in actual.columns]
        st.dataframe(actual[cols].iloc[::-1], use_container_width=True, hide_index=True)
with tab2:
    if missed.empty:
        st.info("No capital-missed opportunities yet.")
    else:
        preferred = ["trade_id","symbol","signal","entry_time","entry","stop_loss","target","quantity","risk","reward","rr","exit_time","exit_price","exit_reason","pnl","status"]
        cols = [c for c in preferred if c in missed.columns]
        st.dataframe(missed[cols].iloc[::-1], use_container_width=True, hide_index=True)
with tab3:
    if signals.empty:
        st.info("No scanner signals yet.")
    else:
        preferred = ["timestamp","symbol","signal","entry","stop_loss","target","risk_reward","actual_risk","position_value","pdc","today_open","today_low","today_high","nifty100_direction","sector","sector_direction","stock_today_direction","previous_day_direction","setup_type","approved","reason"]
        cols = [c for c in preferred if c in signals.columns]
        st.dataframe(signals[cols].iloc[::-1], use_container_width=True, hide_index=True)

st.divider()
st.caption("Read-only analysis. The page never starts the worker and never changes trading state. Actual P&L and hypothetical capital-missed P&L remain separate.")
