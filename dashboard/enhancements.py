"""Additional master-dashboard panels: Dhan diagnostics, CSV download,
strategy comparison, and entry/exit cards. Values are source-derived only.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

STRATEGIES = {
    "S1": "PDH/PDL Sweep + Open Reclaim",
    "S2": "PDH/PDL Breakout + Retest",
    "S3": "PDL/PDH Sweep + Open Reclaim",
    "S4": "Intraday High/Low Breakout",
    "S5": "Direct PDH/PDL Breakout",
}


def _csv(name):
    p = OUTPUTS / name
    try:
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _money(v):
    n = _num(v)
    return f"₹{n:,.2f}" if n is not None else "—"


def _card(label, value):
    return f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"


def _strategy(v):
    s = str(v).upper().strip()
    if s in STRATEGIES:
        return s
    if s.startswith("STRATEGY_"):
        return "S" + s.split("_")[-1]
    return s


def _find(df, names):
    if df.empty:
        return None
    lower = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _dhan_diagnostic():
    """Return a safe Dhan API diagnostic without exposing credentials."""
    def secret(name):
        value = os.getenv(name, "")
        if value:
            return str(value).strip()
        try:
            return str(st.secrets.get(name, "")).strip()
        except Exception:
            return ""

    client_id = secret("DHAN_CLIENT_ID")
    token = secret("DHAN_ACCESS_TOKEN")
    if not client_id or not token:
        return {"status": "NOT CONFIGURED", "detail": "DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN missing"}

    headers = {"Accept": "application/json", "access-token": token, "client-id": client_id}
    try:
        profile = requests.get("https://api.dhan.co/v2/profile", headers=headers, timeout=10)
        try:
            body = profile.json()
        except Exception:
            body = {}
        if profile.status_code != 200:
            code = body.get("errorCode") or body.get("errorType") or profile.status_code
            msg = body.get("errorMessage") or body.get("message") or profile.text[:180]
            return {"status": "ERROR", "detail": f"{code}: {msg}"}
        detail = f"Token: {body.get('tokenValidity','—')} • Data plan: {body.get('dataPlan','—')} • Data validity: {body.get('dataValidity','—')}"

        # Pick one NSE equity from the public master and make an OHLC request.
        master = requests.get(MASTER_URL, timeout=20)
        master.raise_for_status()
        from io import StringIO
        m = pd.read_csv(StringIO(master.text), low_memory=False)
        cols = {str(c).upper(): c for c in m.columns}
        symc = cols.get("SEM_TRADING_SYMBOL") or cols.get("SYMBOL_NAME")
        sidc = cols.get("SEM_SECURITY_ID") or cols.get("SECURITY_ID")
        if not symc or not sidc:
            return {"status": "PROFILE OK / MASTER FORMAT", "detail": detail}
        row = m[m[symc].astype(str).str.upper().eq("TCS")].head(1)
        if row.empty:
            return {"status": "PROFILE OK", "detail": detail}
        sid = int(float(row.iloc[0][sidc]))
        q = requests.post("https://api.dhan.co/v2/marketfeed/ohlc", headers={**headers, "Content-Type": "application/json"}, json={"NSE_EQ": [sid]}, timeout=10)
        try:
            qb = q.json()
        except Exception:
            qb = {}
        if q.status_code != 200:
            code = qb.get("errorCode") or q.status_code
            msg = qb.get("errorMessage") or qb.get("message") or q.text[:180]
            return {"status": "PROFILE OK / QUOTE ERROR", "detail": f"{code}: {msg} • {detail}"}
        item = qb.get("data", {}).get("NSE_EQ", {}).get(str(sid), {})
        ltp = item.get("last_price")
        ohlc = item.get("ohlc") or {}
        return {"status": "Dhan QUOTE OK", "detail": f"TCS LTP {_money(ltp)} • Close {_money(ohlc.get('close'))} • {detail}"}
    except Exception as exc:
        return {"status": "REQUEST ERROR", "detail": f"{type(exc).__name__}: {exc}"}


def render_enhancements():
    now = datetime.now(IST)
    st.markdown("<div class='sec'>🧰 Data, Quotes & Strategy Research</div>", unsafe_allow_html=True)

    diag = _dhan_diagnostic()
    css = "<style>.card{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:9px;min-height:61px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}.value{font-size:.90rem;font-weight:850;color:#f5f7fb;margin-top:4px}</style>"
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(f"<div class='status'><b>📡 Dhan diagnostic: {diag['status']}</b> • {diag['detail']}</div>", unsafe_allow_html=True)

    st.markdown("<div class='sec'>📥 Dhan Master Instrument CSV</div>", unsafe_allow_html=True)
    try:
        r = requests.get(MASTER_URL, timeout=30)
        r.raise_for_status()
        st.download_button("⬇️ Download Dhan Master CSV", r.content, "dhan_scrip_master.csv", "text/csv", key="dhan_master_csv")
        st.caption(f"Source: Dhan public instrument master • fetched {now.strftime('%d %b %Y %H:%M:%S')} IST")
    except Exception as exc:
        st.error(f"Dhan master CSV could not be downloaded: {type(exc).__name__}: {exc}")

    trades = _csv("trades.csv")
    signals = _csv("signals.csv")
    if not trades.empty and "strategy" in trades.columns:
        trades["strategy"] = trades["strategy"].map(_strategy)
    if not signals.empty and "strategy" in signals.columns:
        signals["strategy"] = signals["strategy"].map(_strategy)

    st.markdown("<div class='sec'>⚖️ S1–S5 Strategy Comparison</div>", unsafe_allow_html=True)
    rows = []
    for s, name in STRATEGIES.items():
        t = trades[trades["strategy"].astype(str).eq(s)].copy() if not trades.empty and "strategy" in trades.columns else pd.DataFrame()
        pnl_col = _find(t, ["pnl", "P&L", "profit_loss"])
        pnl = pd.to_numeric(t[pnl_col], errors="coerce").dropna() if pnl_col else pd.Series(dtype=float)
        wins = int((pnl > 0).sum()); losses = int((pnl < 0).sum())
        rows.append({"Strategy": s, "Name": name, "Taken": len(t), "Wins": wins, "Losses": losses,
                     "Win %": round(wins / (wins + losses) * 100, 1) if wins + losses else None,
                     "P&L": round(float(pnl.sum()), 2) if len(pnl) else None,
                     "Status": "DATA AVAILABLE" if len(t) else "NO TAKEN-TRADE DATA"})
    comp = pd.DataFrame(rows)
    st.dataframe(comp, width="stretch", hide_index=True)
    st.download_button("⬇️ CSV — S1–S5 Strategy Comparison", comp.to_csv(index=False).encode(), "strategy_comparison.csv", "text/csv", key="strategy_comparison_csv")

    st.markdown("<div class='sec'>🎯 Entry / SL / Target / Exit</div>", unsafe_allow_html=True)
    if trades.empty:
        st.info("No taken-trade records are available yet. Entry/SL/Target/Exit cards will populate from the actual trades ledger.")
        return

    # Show the latest five actual trade records as compact cards. Never invent a value.
    time_col = _find(trades, ["exit_time", "entry_time", "timestamp", "time", "datetime"])
    view = trades.copy()
    if time_col:
        view["__sort"] = pd.to_datetime(view[time_col], errors="coerce")
        view = view.sort_values("__sort", ascending=False)
    view = view.head(5)

    for idx, (_, row) in enumerate(view.iterrows()):
        strategy = str(row.get("strategy", "—"))
        symbol = str(row.get("symbol", row.get("Symbol", "—")))
        entry = row.get(_find(trades, ["entry_price", "entry", "buy_price", "entry_ltp"]), "—") if _find(trades, ["entry_price", "entry", "buy_price", "entry_ltp"]) else "—"
        sl = row.get(_find(trades, ["stop_loss", "sl", "stoploss"]), "—") if _find(trades, ["stop_loss", "sl", "stoploss"]) else "—"
        target = row.get(_find(trades, ["target_price", "target", "take_profit", "tp"]), "—") if _find(trades, ["target_price", "target", "take_profit", "tp"]) else "—"
        exitp = row.get(_find(trades, ["exit_price", "exit", "sell_price", "exit_ltp"]), "—") if _find(trades, ["exit_price", "exit", "sell_price", "exit_ltp"]) else "—"
        et = row.get(_find(trades, ["entry_time", "entry_timestamp"]), "—") if _find(trades, ["entry_time", "entry_timestamp"]) else "—"
        xt = row.get(_find(trades, ["exit_time", "exit_timestamp"]), "—") if _find(trades, ["exit_time", "exit_timestamp"]) else "—"
        pnl = row.get(_find(trades, ["pnl", "P&L", "profit_loss"]), "—") if _find(trades, ["pnl", "P&L", "profit_loss"]) else "—"
        cols = st.columns(7)
        vals = [("SYMBOL", symbol), ("STRATEGY", strategy), ("ENTRY", entry), ("SL", sl), ("TARGET", target), ("EXIT", exitp), ("P&L", _money(pnl))]
        for col, (label, value) in zip(cols, vals):
            with col:
                st.markdown(_card(label, value), unsafe_allow_html=True)
        st.caption(f"Entry time: {et} • Exit time: {xt}")
