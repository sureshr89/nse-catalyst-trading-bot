"""Read-only visual strategy research dashboard."""
from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "outputs" / "trades.csv"
SIGNALS_FILE = PROJECT_ROOT / "outputs" / "signals.csv"
STARTING_CAPITAL = 250000.0

st.set_page_config(page_title="NSE Catalyst | Analysis", page_icon="📊", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: .7rem; padding-bottom: 2rem; max-width: 1500px;}
.analysis-title {font-size:2.15rem; font-weight:750; margin-bottom:.15rem;}
.analysis-subtitle {font-size:1rem; opacity:.78; margin-bottom:1rem;}
.section-title {font-size:1.35rem; font-weight:700; margin-top:1.5rem; margin-bottom:.65rem;}
[data-testid="stMetric"] {padding:.8rem .9rem; border:1px solid rgba(128,128,128,.22); border-radius:12px; min-height:88px;}
[data-testid="stMetricLabel"] {font-size:.9rem!important;}
[data-testid="stMetricValue"] {font-size:1.25rem!important;}
[data-testid="stDataFrame"] {font-size:.88rem!important;}
.js-plotly-plot {width:100%!important;}
@media(max-width:768px){
  .analysis-title{font-size:1.75rem;}
  .analysis-subtitle{font-size:.95rem;}
  .section-title{font-size:1.2rem;}
  [data-testid="stMetricLabel"]{font-size:.82rem!important;}
  [data-testid="stMetricValue"]{font-size:1.05rem!important;}
}
</style>
""", unsafe_allow_html=True)


def load_csv(path):
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


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
    if all(c in df.columns for c in ["risk", "entry", "stop_loss", "quantity"]):
        mask = df["risk"] <= 0
        df.loc[mask, "risk"] = (df.loc[mask, "entry"] - df.loc[mask, "stop_loss"]).abs() * df.loc[mask, "quantity"]
    if all(c in df.columns for c in ["reward", "target", "entry", "quantity"]):
        mask = df["reward"] <= 0
        df.loc[mask, "reward"] = (df.loc[mask, "target"] - df.loc[mask, "entry"]).abs() * df.loc[mask, "quantity"]
    if "risk" in df.columns and "reward" in df.columns:
        mask = df["risk"] > 0
        df.loc[mask, "rr"] = df.loc[mask, "reward"] / df.loc[mask, "risk"]
    df["Result"] = df["pnl"].apply(lambda x: "WIN" if x > 0 else "LOSS" if x < 0 else "FLAT")
    return df


def stats(df):
    if df.empty:
        return {"Trades":0,"Wins":0,"Losses":0,"Flat":0,"Win Rate %":0.0,"P&L":0.0,"Avg P&L":0.0,"Avg Win":0.0,"Avg Loss":0.0,"Expectancy":0.0,"Profit Factor":0.0,"Avg Risk":0.0,"Avg R:R":0.0}
    pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gp, gl = float(wins.sum()), abs(float(losses.sum()))
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


def make_pie(df, column, title, height=330):
    if df.empty or column not in df.columns:
        return
    counts = df[column].fillna("UNKNOWN").astype(str).value_counts().reset_index()
    counts.columns = [column, "Count"]
    fig = px.pie(counts, names=column, values="Count", hole=.45, title=title)
    fig.update_layout(height=height, margin=dict(l=8,r=8,t=55,b=8), legend_title_text="", font=dict(size=12))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})


def finish_chart(fig, height=350):
    fig.update_layout(height=height, margin=dict(l=10,r=10,t=55,b=12), font=dict(size=12), title_font=dict(size=16))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})


trades = prepare(load_csv(TRADES_FILE))
signals = load_csv(SIGNALS_FILE)

if not trades.empty and "status" in trades.columns:
    status_col = trades["status"].astype(str).str.upper()
    actual = prepare(trades[status_col == "CLOSED"].copy())
    missed = prepare(trades[status_col.isin(["MISSED_CAPITAL_OPEN", "MISSED_CAPITAL_CLOSED"])].copy())
else:
    actual, missed = pd.DataFrame(), pd.DataFrame()

missed_closed = missed[missed["status"].astype(str).str.upper() == "MISSED_CAPITAL_CLOSED"].copy() if not missed.empty else pd.DataFrame()
a = stats(actual)
m = stats(missed_closed)

st.markdown('<div class="analysis-title">📊 Strategy Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="analysis-subtitle">Actual closed trades are the official performance result. Capital-missed trades remain hypothetical and never change the account P&L.</div>', unsafe_allow_html=True)

# ------------------------- OVERALL PERFORMANCE -------------------------
st.markdown('<div class="section-title">💰 Overall Performance</div>', unsafe_allow_html=True)
overall_pnl = a["P&L"]
equity = STARTING_CAPITAL + overall_pnl
return_pct = overall_pnl / STARTING_CAPITAL * 100

c1,c2,c3,c4 = st.columns(4)
c1.metric("Fixed Starting Capital", f"₹{STARTING_CAPITAL:,.0f}")
c2.metric("Overall P&L", f"₹{overall_pnl:,.2f}")
c3.metric("Current Equity", f"₹{equity:,.2f}")
c4.metric("Overall Return", f"{return_pct:+.2f}%")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Trading Days", "0")
c2.metric("Profitable Days", "0")
c3.metric("Loss Days", "0")
c4.metric("Closed Trades", a["Trades"])

# ------------------------- DAILY / MONTHLY P&L -------------------------
st.markdown('<div class="section-title">📅 Daily & Monthly P&L</div>', unsafe_allow_html=True)
if actual.empty:
    st.info("No closed actual trades yet. Daily and monthly performance will appear automatically after trades close.")
else:
    dated = actual.copy()
    time_col = next((x for x in ["exit_time", "entry_time", "timestamp"] if x in dated.columns), None)
    if time_col:
        dated["_date"] = pd.to_datetime(dated[time_col], errors="coerce").dt.date
    else:
        dated["_date"] = pd.NaT
    dated = dated[dated["_date"].notna()].copy()

    if dated.empty:
        st.warning("Closed trades exist, but no usable trade date was found for daily/monthly accounting.")
    else:
        daily = dated.groupby("_date", as_index=False)["pnl"].sum().sort_values("_date")
        daily["Cumulative P&L"] = daily["pnl"].cumsum()
        daily["Equity"] = STARTING_CAPITAL + daily["Cumulative P&L"]
        daily["Result"] = daily["pnl"].apply(lambda x: "Profit" if x > 0 else "Loss" if x < 0 else "Flat")
        profitable_days = int((daily["pnl"] > 0).sum())
        loss_days = int((daily["pnl"] < 0).sum())

        # Replace the placeholder day metrics above with actual values.
        st.markdown(f"**{len(daily)} trading days • {profitable_days} profitable • {loss_days} loss days**")
        left, right = st.columns(2)
        with left:
            fig = px.bar(daily, x="_date", y="pnl", title="Daily P&L", labels={"_date":"Date","pnl":"P&L (₹)"})
            finish_chart(fig, 360)
        with right:
            fig = px.line(daily, x="_date", y="Cumulative P&L", markers=True, title="Cumulative P&L", labels={"_date":"Date","Cumulative P&L":"₹"})
            finish_chart(fig, 360)

        monthly = dated.copy()
        monthly["Month"] = pd.to_datetime(monthly["_date"]).dt.to_period("M").astype(str)
        monthly = monthly.groupby("Month", as_index=False)["pnl"].sum().sort_values("Month")
        monthly["Cumulative P&L"] = monthly["pnl"].cumsum()
        monthly["Equity"] = STARTING_CAPITAL + monthly["Cumulative P&L"]
        monthly["Return %"] = monthly["pnl"] / STARTING_CAPITAL * 100

        left, right = st.columns(2)
        with left:
            fig = px.bar(monthly, x="Month", y="pnl", title="Monthly Net P&L", labels={"pnl":"Net P&L (₹)"})
            finish_chart(fig, 350)
        with right:
            fig = px.line(monthly, x="Month", y="Equity", markers=True, title="Equity Over Months", labels={"Equity":"₹"})
            finish_chart(fig, 350)

        daily_display = daily.rename(columns={"_date":"Date", "pnl":"Daily P&L"})[["Date","Daily P&L","Cumulative P&L","Equity","Result"]]
        monthly_display = monthly.rename(columns={"pnl":"Net P&L"})[["Month","Net P&L","Cumulative P&L","Equity","Return %"]]
        st.subheader("Daily Account Ledger")
        st.dataframe(daily_display.iloc[::-1], use_container_width=True, hide_index=True)
        st.subheader("Monthly Account Summary")
        st.dataframe(monthly_display.iloc[::-1], use_container_width=True, hide_index=True)
        st.caption("Capital stays fixed at ₹2,50,000 for this dashboard. P&L is accumulated separately; equity is shown as fixed capital + cumulative realized P&L.")

# ------------------------------ TOP KPIs -------------------------------
st.markdown('<div class="section-title">📌 Trade & Strategy KPIs</div>', unsafe_allow_html=True)
c1,c2,c3,c4 = st.columns(4)
c1.metric("Actual Trades", a["Trades"])
c2.metric("Win Rate", f'{a["Win Rate %"]:.1f}%')
c3.metric("Average P&L / Trade", f'₹{a["Avg P&L"]:,.2f}')
c4.metric("Profit Factor", f'{a["Profit Factor"]:.2f}')
c1,c2,c3,c4 = st.columns(4)
c1.metric("Wins", a["Wins"])
c2.metric("Losses", a["Losses"])
c3.metric("Average Win", f'₹{a["Avg Win"]:,.2f}')
c4.metric("Average Loss", f'₹{a["Avg Loss"]:,.2f}')

# -------------------------- PERFORMANCE CURVES -------------------------
st.markdown('<div class="section-title">📈 Trade-Level Performance</div>', unsafe_allow_html=True)
if actual.empty:
    st.info("No closed actual trades yet.")
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
        finish_chart(fig, 350)
    with right:
        fig = px.bar(curve, x="Trade #", y="pnl", title="Individual Trade P&L")
        finish_chart(fig, 350)
    left, right = st.columns(2)
    with left:
        fig = px.line(curve, x="Trade #", y="Drawdown", markers=True, title="Drawdown")
        finish_chart(fig, 330)
    with right:
        fig = px.line(curve, x="Trade #", y="pnl", markers=True, title="Trade P&L Sequence")
        finish_chart(fig, 330)

# ----------------------------- OUTCOMES --------------------------------
st.markdown('<div class="section-title">🎯 Outcome Analysis</div>', unsafe_allow_html=True)
if actual.empty:
    st.info("No actual trade outcomes available yet.")
else:
    left, right = st.columns(2)
    with left:
        make_pie(actual.assign(Outcome=actual["Result"]), "Outcome", "Actual Win / Loss / Flat")
    with right:
        make_pie(actual, "exit_reason", "Actual Exit Reasons")
    outcome = pd.DataFrame([{
        "Trades":a["Trades"],"Wins":a["Wins"],"Losses":a["Losses"],"Flat":a["Flat"],"Win Rate %":a["Win Rate %"],
        "Average P&L":a["Avg P&L"],"Average Win":a["Avg Win"],"Average Loss":a["Avg Loss"],"Expectancy":a["Expectancy"],
        "Profit Factor":a["Profit Factor"],"Average Risk":a["Avg Risk"],"Average R:R":a["Avg R:R"]
    }])
    st.dataframe(outcome, use_container_width=True, hide_index=True)

# ------------------------- SIDE / EXIT / STOCK -------------------------
st.markdown('<div class="section-title">🏷️ Where the Strategy Works</div>', unsafe_allow_html=True)
if not actual.empty:
    charts = []
    side = group_stats(actual, "signal")
    if not side.empty:
        charts.append(("P&L by BUY / SELL", px.bar(side, x="signal", y="P&L", text="Trades", title="P&L by BUY / SELL")))
    exit_stats = group_stats(actual, "exit_reason")
    if not exit_stats.empty:
        charts.append(("P&L by Exit Reason", px.bar(exit_stats, x="exit_reason", y="P&L", text="Trades", title="P&L by Exit Reason")))
    for i in range(0, len(charts), 2):
        left, right = st.columns(2)
        with left:
            finish_chart(charts[i][1], 340)
        if i + 1 < len(charts):
            with right:
                finish_chart(charts[i+1][1], 340)

    stock_stats = group_stats(actual, "symbol")
    if not stock_stats.empty:
        left, right = st.columns(2)
        with left:
            fig = px.bar(stock_stats.head(20), x="symbol", y="P&L", text="Trades", title="Top 20 Stocks by Actual P&L")
            finish_chart(fig, 380)
        with right:
            st.dataframe(stock_stats[["symbol","Trades","Wins","Losses","Win Rate %","P&L"]], use_container_width=True, hide_index=True, height=380)

# ------------------------------- RISK ---------------------------------
st.markdown('<div class="section-title">⚖️ Risk & R:R Analysis</div>', unsafe_allow_html=True)
if not actual.empty:
    risk_df = actual.copy()
    left, right = st.columns(2)
    with left:
        fig = px.scatter(risk_df, x="risk", y="pnl", size="quantity" if "quantity" in risk_df else None, hover_name="symbol", hover_data=["signal","rr"], title="Risk vs Actual P&L")
        finish_chart(fig, 360)
    with right:
        fig = px.scatter(risk_df, x="rr", y="pnl", hover_name="symbol", hover_data=["signal","risk"], title="R:R vs Actual P&L")
        finish_chart(fig, 360)

# ------------------------------ TIMING --------------------------------
st.markdown('<div class="section-title">⏱️ Signal & Trade Timing</div>', unsafe_allow_html=True)
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
            finish_chart(fig, 350)
    if "approved" in sig.columns:
        approved = sig["approved"].astype(str).str.upper().isin(["TRUE","1","YES"])
        left, right = st.columns(2)
        with left:
            make_pie(pd.DataFrame({"Status":["Approved","Rejected"],"Count":[int(approved.sum()),int((~approved).sum())]}), "Status", "Signal Approval", 330)
        with right:
            if "reason" in sig.columns:
                reason_counts = sig["reason"].fillna("No reason").astype(str).value_counts().head(12).reset_index()
                reason_counts.columns = ["Reason","Count"]
                fig = px.bar(reason_counts, x="Count", y="Reason", orientation="h", title="Top Signal Reasons")
                finish_chart(fig, 330)

# ------------------------ MARKET ALIGNMENT -----------------------------
st.markdown('<div class="section-title">🌐 Market / Sector / Setup Analysis</div>', unsafe_allow_html=True)
if not actual.empty:
    market_charts = []
    for col in ["nifty100_direction", "sector_direction", "stock_today_direction", "previous_day_direction", "setup_type"]:
        if col in actual.columns and actual[col].notna().any():
            table = group_stats(actual, col)
            if not table.empty:
                fig = px.bar(table, x=col, y="P&L", text="Trades", title=f"Actual P&L by {col.replace('_',' ').title()}")
                market_charts.append(fig)
    for i in range(0, len(market_charts), 2):
        left, right = st.columns(2)
        with left:
            finish_chart(market_charts[i], 330)
        if i + 1 < len(market_charts):
            with right:
                finish_chart(market_charts[i+1], 330)

# --------------------- ACTUAL VS MISSED CAPITAL ------------------------
st.markdown('<div class="section-title">🧪 Actual vs Capital-Missed</div>', unsafe_allow_html=True)
comparison = pd.DataFrame([
    {"Category":"Actual trades", **a},
    {"Category":"Capital-missed resolved", **m},
])
st.dataframe(comparison, use_container_width=True, hide_index=True)
if not missed.empty:
    left, right = st.columns(2)
    with left:
        if not missed_closed.empty:
            fig = px.bar(pd.DataFrame({"Category":["Actual","Missed due to capital"],"P&L":[a["P&L"],m["P&L"]]}), x="Category", y="P&L", title="Realized vs Hypothetical P&L")
            finish_chart(fig, 340)
    with right:
        make_pie(pd.DataFrame({"Category":["Actual","Missed due to capital"],"Count":[len(actual),len(missed_closed)]}), "Category", "Actual vs Resolved Capital-Missed", 340)
    st.caption("Capital-missed results are hypothetical. They never change actual trading P&L.")

# ----------------------------- TABLES ----------------------------------
st.markdown('<div class="section-title">📋 Detailed Research Data</div>', unsafe_allow_html=True)
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
st.caption("Read-only analysis. Fixed starting capital: ₹2,50,000. Official performance uses only closed actual trades; capital-missed trades are shown separately.")
