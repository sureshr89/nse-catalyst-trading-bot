"""NSE Catalyst master dashboard — presentation only; strategy logic remains in market modules."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")


def num(x, d=None):
    try:
        v = float(x)
        return v if pd.notna(v) else d
    except Exception:
        return d


def pct(x):
    v = num(x)
    return f"{v:+.2f}%" if v is not None else "—"


def card(label, value):
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'


def read_csv(name):
    p = OUTPUTS / name
    try:
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def normalize_trade_csv(df):
    """Keep one master CSV with a stable, complete trade-detail schema."""
    required = [
        "date", "strategy", "symbol", "side", "entry_time", "exit_time",
        "entry_price", "exit_price", "stop_loss", "target", "quantity",
        "risk", "pnl", "exit_reason", "nifty500_pct", "sector_pct",
        "ad_ratio", "ad_coverage", "previous_candle", "pdh", "pdl",
        "today_open", "today_high", "today_low", "signal_time", "status",
        "notes",
    ]
    out = df.copy()
    aliases = {
        "Strategy": "strategy", "strategy_name": "strategy", "ticker": "symbol",
        "entry": "entry_price", "exit": "exit_price", "qty": "quantity",
        "sl": "stop_loss", "tp": "target", "reason": "exit_reason",
        "timestamp": "signal_time", "date_time": "signal_time",
    }
    for old, new in aliases.items():
        if old in out.columns and new not in out.columns:
            out[new] = out[old]
    for col in required:
        if col not in out.columns:
            out[col] = ""
    # Preserve every original column after the stable fields, so no journal detail is lost.
    extras = [c for c in out.columns if c not in required]
    return out[required + extras]


st.markdown("""
<style>
.stApp{background:#000!important;color:#f5f7fb}
.block-container{max-width:1450px;padding:.75rem .8rem 2rem}
.title{font-size:clamp(1.55rem,4vw,2.5rem);font-weight:900;margin:0 0 3px;color:#f5f7fb}
.sub{font-size:.76rem;color:#9fb1ca;margin-bottom:12px}
.sec{font-size:1.12rem;font-weight:900;color:#f5f7fb;margin:16px 0 8px}
.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}
.card,.status{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:10px}
.card{min-height:61px}.label{font-size:.56rem;font-weight:850;color:#9fb1ca;text-transform:uppercase}
.value{font-size:.96rem;font-weight:850;color:#f5f7fb;margin-top:4px}
.status{margin:7px 0;color:#d9e3f1;font-size:.78rem}
.strategy{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:11px;margin-bottom:7px;color:#f5f7fb}
.strategy b{font-size:.9rem}.strategy span{color:#9fb1ca;font-size:.76rem}
.strategy .trade{float:right;font-size:.68rem;font-weight:900;padding:4px 7px;border-radius:8px;background:#15263d;color:#9fb1ca}
.tip{background:#101b2b;border:1px solid #294367;border-radius:11px;padding:14px;font-size:.9rem;font-weight:700;color:#f5f7fb}
@media(max-width:850px){.grid6{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.grid6{grid-template-columns:repeat(2,1fr)}}
</style>
""", unsafe_allow_html=True)


@st.fragment(run_every="15s")
def live_dashboard():
    now = datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured, dhan_status
        market = BREADTH.snapshot(force=False)
        dhan_ok = dhan_configured()
        api_status = dhan_status()
    except Exception as exc:
        market = {"complete": False, "sector_complete": False, "reason": f"{type(exc).__name__}: {exc}", "evaluated": 0, "total": 500, "quote_rows": pd.DataFrame()}
        dhan_ok = False
        api_status = {"ok": False, "stage": "IMPORT", "message": str(exc), "received": 0, "requested": 0}

    trades_raw = read_csv("trades.csv")
    signals = read_csv("signals.csv")
    trades = normalize_trade_csv(trades_raw)

    # One master file only. It contains complete trade fields and signal records without deleting extras.
    master_parts = []
    if not trades.empty:
        t = trades.copy(); t.insert(0, "RecordType", "TRADE"); master_parts.append(t)
    if not signals.empty:
        s = signals.copy(); s.insert(0, "RecordType", "SIGNAL"); master_parts.append(s)
    master_csv = pd.concat(master_parts, ignore_index=True, sort=False) if master_parts else normalize_trade_csv(pd.DataFrame())

    n = market.get("nifty500_change_pct"); sec = market.get("sector_alignment_pct"); ad = market.get("ad_ratio")
    evaln = int(market.get("evaluated", 0) or 0); sp = int(market.get("sector_priced", 0) or 0)
    buy = bool(market.get("complete") and market.get("sector_complete") and num(n, 0) > 0 and num(sec, 0) > 0 and num(ad, 0) > 1)
    sell = bool(market.get("complete") and market.get("sector_complete") and num(n, 0) < 0 and num(sec, 0) < 0 and num(ad, 2) < 1)
    bias = "🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

    st.markdown('<div class="title">📊 NSE Catalyst — Master Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan data • App time {now.strftime("%d %b %Y %H:%M:%S")} IST</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec">🎯 Master Market Alignment</div>', unsafe_allow_html=True)
    st.markdown('<div class="grid6">' + "".join([
        card("NIFTY 500", pct(n)), card("SECTORS", pct(sec)),
        card("A/D RATIO", f"{ad:.2f}" if ad is not None else "WAITING"),
        card("BREADTH", f"{evaln}/500"), card("SECTOR DATA", f"{sp}/500"), card("MASTER BIAS", bias)
    ]) + '</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="status"><b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if api_status.get("ok") else "WAIT/ERROR"} • Quotes {api_status.get("received",0)}/{api_status.get("requested",0)} • Auto refresh: 15s</div>', unsafe_allow_html=True)

    # S1-S5 are displayed from the actual journal, not invented trade signals.
    st.markdown('<div class="sec">⚡ S1–S5 STRATEGIES & TRADES</div>', unsafe_allow_html=True)
    strategies = [
        ("S1", "Sweep + Open Reclaim", "Liquidity sweep followed by reclaim of the open."),
        ("S2", "Breakout + Retest", "Breakout must hold on the retest before entry."),
        ("S3", "Reverse Sweep + Reclaim", "Failed sweep with confirmation back through the level."),
        ("S4", "Intraday High/Low Breakout", "Break of the active session high/low with confirmation."),
        ("S5", "Direct PDH/PDL Breakout", "Previous-day high/low breakout with confirmation."),
    ]
    strat_col = next((c for c in ["strategy", "strategy_name", "Strategy"] if c in trades.columns), "strategy")
    for code, name, desc in strategies:
        if not trades.empty:
            mask = trades[strat_col].astype(str).str.upper().str.contains(code, na=False)
            st_today = trades[mask]
            count = len(st_today)
            last = st_today.iloc[-1] if count else None
        else:
            count = 0; last = None
        if last is not None:
            side = str(last.get("side", "")).upper()
            pnl_v = num(last.get("pnl"), 0)
            summary = f"{side or 'TRADE'} • P&L ₹{pnl_v:,.0f}"
        else:
            summary = "NO TRADE"
        st.markdown(f'<div class="strategy"><span class="trade">{count} trade(s) • {summary}</span><b>{code} • {name}</b><br><span>{desc}</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">📥 MASTER DOWNLOAD</div>', unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV", master_csv.to_csv(index=False).encode("utf-8"), "nse_catalyst_master.csv", "text/csv", use_container_width=True, key="master_csv")

    st.markdown('<div class="sec">🧠 Daily Analysis & Journal</div>', unsafe_allow_html=True)
    today = trades.copy()
    dc = next((c for c in ["exit_time", "entry_time", "signal_time", "date"] if c in today.columns), None)
    if dc and not today.empty:
        dt = pd.to_datetime(today[dc], errors="coerce"); today = today[dt.dt.date == now.date()]
    pnl = pd.to_numeric(today.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0)
    win_rate = f"{(pnl > 0).mean() * 100:.1f}%" if len(pnl) else "—"
    st.markdown('<div class="grid6">' + "".join([
        card("TRADES", len(today)), card("WINS", int((pnl > 0).sum())), card("LOSSES", int((pnl < 0).sum())),
        card("WIN RATE", win_rate), card("TODAY P&L", f"₹{pnl.sum():,.0f}"),
        card("TODAY DD", f"₹{min(0, pnl.cumsum().min()) if len(pnl) else 0:,.0f}")
    ]) + '</div>', unsafe_allow_html=True)
    if not today.empty:
        st.dataframe(today, width="stretch", hide_index=True)
    else:
        st.info("No taken trades recorded today.")

    st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
    tips = ["Follow the setup, not the emotion.", "Protect capital first; profits come second.", "Wait for confirmation before entering.", "One disciplined trade is better than many emotional trades.", "Never chase a missed entry."]
    st.markdown(f'<div class="tip">💡 {tips[now.date().toordinal() % len(tips)]}</div>', unsafe_allow_html=True)
    st.caption("NSE Catalyst • paper trading only • refreshed every 15 seconds")


live_dashboard()
