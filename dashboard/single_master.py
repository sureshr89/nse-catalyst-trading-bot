"""NSE Catalyst production dashboard.

Compact production presentation layer for the NIFTY 500 paper-trading engine.
It consumes the shared 15-second snapshot; it does not fetch constituent prices
independently. The dashboard intentionally shows only market alignment, sector
summary cards, S1-S5 strategy cards, CSV download and the daily tip.
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


def read_csv(name):
    path = OUTPUTS / name
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def num(value, default=0.0):
    try:
        value = float(value)
        return value if pd.notna(value) else default
    except Exception:
        return default


def fmt(value):
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def pct(value):
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):,.2f}%"
    except Exception:
        return str(value)


def first(row, *names, default=""):
    if row is None:
        return default
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and str(value).strip() not in {"", "nan", "NaT"}:
                return value
    return default


def card(label, value, emphasis=""):
    color = {"buy": "#67e8a5", "sell": "#ff7b7b", "wait": "#ffd166"}.get(emphasis, "#ffffff")
    return (
        '<div style="background:#101b2b;border:1px solid #294367;border-radius:12px;'
        'padding:12px;min-height:72px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:10px;font-weight:900;color:#cbd5e1;text-transform:uppercase;">{label}</div>'
        f'<div style="font-size:19px;font-weight:900;color:{color};margin-top:6px;line-height:1.15;">{value}</div>'
        '</div>'
    )


def card_grid(items):
    return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:8px;width:100%;margin-bottom:8px;">' + "".join(items) + '</div>'


def strategy_card(strategy, state, state_color, cells):
    """Responsive, colorful strategy card; presentation only, no trading logic."""
    palette = {
        "S1": ("#22c55e", "#064e3b", "↩️", "PDH/PDL SWEEP REVERSAL"),
        "S2": ("#38bdf8", "#0c4a6e", "🔁", "BREAKOUT + RETEST"),
        "S3": ("#f59e0b", "#78350f", "🎯", "INSIDE RANGE REVERSAL"),
        "S4": ("#a78bfa", "#4c1d95", "⚡", "INTRADAY BREAKOUT"),
        "S5": ("#f43f5e", "#881337", "🚀", "PDH/PDL BREAKOUT"),
    }
    accent, accent_dark, icon, subtitle = palette.get(strategy, ("#64748b", "#1e293b", "📊", "STRATEGY"))
    state_bg = "#064e3b" if state in {"CLOSED", "TRADE OPEN"} else "#0c4a6e" if state == "SIGNAL" else "#713f12" if state == "WAITING" else "#1e293b"
    html = "".join(
        f'<div class="strategy-cell">'
        f'<div class="strategy-label">{label}</div>'
        f'<div class="strategy-value">{value or "—"}</div></div>'
        for label, value in cells
    )
    return (
        f'<div class="strategy-card" style="--strategy-accent:{accent};--strategy-dark:{accent_dark};">'
        f'<div class="strategy-header">'
        f'<div class="strategy-title"><span class="strategy-icon">{icon}</span>'
        f'<div><div class="strategy-code">{strategy}</div><div class="strategy-subtitle">{subtitle}</div></div></div>'
        f'<span class="strategy-state" style="color:{state_color};background:{state_bg};">{state}</span>'
        f'</div>'
        f'<div class="strategy-grid">{html}</div>'
        f'</div>'
    )


st.markdown("""
<style>
.stApp{background:#000!important;color:#fff!important}
.block-container{max-width:1450px;padding:.7rem .8rem 2rem}
.stCaption,.stCaption p{color:#cbd5e1!important}

/* Responsive S1-S5 cards: presentation only. */
.strategy-card{
  width:100%;box-sizing:border-box;overflow:hidden;
  background:linear-gradient(145deg,#0b1422 0%,#101b2b 62%,var(--strategy-dark) 180%);
  border:1px solid #294367;border-left:5px solid var(--strategy-accent);
  border-radius:16px;padding:14px;margin:10px 0;
  box-shadow:0 8px 24px rgba(0,0,0,.24);
}
.strategy-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}
.strategy-title{display:flex;align-items:center;gap:10px;min-width:0;}
.strategy-icon{font-size:25px;line-height:1;filter:drop-shadow(0 2px 6px rgba(255,255,255,.15));}
.strategy-code{font-size:21px;font-weight:950;line-height:1;color:#fff;}
.strategy-subtitle{font-size:10px;font-weight:850;letter-spacing:.08em;color:#b9c7d9;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.strategy-state{font-size:11px;font-weight:950;letter-spacing:.03em;padding:7px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.12);white-space:nowrap;}
.strategy-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;}
.strategy-cell{background:rgba(16,27,43,.92);border:1px solid rgba(80,110,145,.35);border-radius:10px;padding:9px;min-width:0;box-sizing:border-box;}
.strategy-label{font-size:9px;font-weight:900;letter-spacing:.07em;text-transform:uppercase;color:#91a4ba;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.strategy-value{font-size:14px;font-weight:900;color:#f8fafc;margin-top:5px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.strategy-cell:hover{border-color:var(--strategy-accent);transform:translateY(-1px);transition:.15s ease;}

@media (min-width:1200px){.strategy-grid{grid-template-columns:repeat(6,minmax(0,1fr));}}
@media (min-width:850px) and (max-width:1199px){.strategy-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
@media (max-width:849px){
  .block-container{padding:.55rem .55rem 1.5rem;}
  .strategy-card{padding:11px;border-radius:14px;margin:8px 0;}
  .strategy-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;}
  .strategy-code{font-size:19px;}
  .strategy-icon{font-size:22px;}
  .strategy-subtitle{font-size:9px;}
  .strategy-state{font-size:10px;padding:6px 8px;}
  .strategy-cell{padding:8px;}
  .strategy-value{font-size:13px;}
}
@media (max-width:430px){
  .strategy-header{align-items:flex-start;}
  .strategy-title{gap:7px;}
  .strategy-grid{grid-template-columns:1fr 1fr;}
  .strategy-subtitle{max-width:190px;}
  .strategy-state{font-size:9px;padding:5px 7px;}
  .strategy-label{font-size:8px;}
  .strategy-value{font-size:12px;}
}
</style>
""", unsafe_allow_html=True)


@st.fragment(run_every="15s")
def live_dashboard():
    now = datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured, dhan_status, index_quote
        market = BREADTH.snapshot(force=False)
        raw_index = index_quote("NIFTY 500")
        if raw_index:
            ltp = num(raw_index.get("LTP"))
            net = num(raw_index.get("NetChange"))
            prev = num(raw_index.get("PreviousClose"))
            if ltp > 0 and prev > 0:
                market["nifty500_ltp"] = ltp
                market["nifty500_net_change"] = net
                market["nifty500_previous_close"] = prev
                market["nifty500_change_pct"] = net / prev * 100
        dhan_ok = dhan_configured()
        api_status = dhan_status()
    except Exception as exc:
        market = {"complete": False, "sector_complete": False, "evaluated": 0, "sector_priced": 0,
                  "nifty500_change_pct": None, "ad_ratio": None, "advances": 0, "declines": 0,
                  "unchanged": 0, "positive_sectors": 0, "negative_sectors": 0,
                  "reason": f"{type(exc).__name__}: {exc}", "quote_rows": pd.DataFrame()}
        dhan_ok = False
        api_status = {"ok": False, "message": str(exc)}
        raw_index = None

    trades_all = read_csv("trades.csv")
    signals_all = read_csv("signals.csv")
    today = now.date()

    def today_rows(df, columns):
        if df.empty:
            return df
        col = next((c for c in columns if c in df.columns), None)
        if not col:
            return df
        d = pd.to_datetime(df[col], errors="coerce", utc=True)
        try:
            d = d.dt.tz_convert(IST)
        except Exception:
            pass
        return df[d.dt.date == today]

    trades_today = today_rows(trades_all, ["exit_time", "entry_time", "market_entry_time", "trigger_entry_time"])
    signals_today = today_rows(signals_all, ["timestamp", "entry_time", "logged_at"])

    complete = bool(market.get("complete"))
    sector_complete = bool(market.get("sector_complete"))
    n = market.get("nifty500_change_pct") if complete else None
    ad = market.get("ad_ratio") if complete else None
    evaln = int(market.get("evaluated", 0) or 0) if complete else 0
    sp = int(market.get("sector_priced", 0) or 0) if sector_complete else 0
    advances = int(market.get("advances", 0) or 0) if complete else 0
    declines = int(market.get("declines", 0) or 0) if complete else 0
    unchanged = int(market.get("unchanged", 0) or 0) if complete else 0
    positive_sectors = int(market.get("positive_sectors", 0) or 0) if sector_complete else 0
    negative_sectors = int(market.get("negative_sectors", 0) or 0) if sector_complete else 0
    quote_rows = market.get("quote_rows")
    quote_count = len(quote_rows) if isinstance(quote_rows, pd.DataFrame) else evaln

    buy = bool(complete and sector_complete and num(n) > 0 and positive_sectors > negative_sectors and num(ad) > 1)
    sell = bool(complete and sector_complete and num(n) < 0 and negative_sectors > positive_sectors and num(ad, 2) < 1)
    bias = "🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

    st.markdown('<div style="font-size:30px;font-weight:950;color:#fff;">📊 NSE Catalyst — Master Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:12px;color:#d5dbe5;margin-bottom:12px;">NIFTY 500 • PAPER TRADING ONLY • Dhan • {now.strftime("%d %b %Y %H:%M:%S")} IST • auto refresh 15s</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:19px;font-weight:950;color:#fff;margin:16px 0 9px;">🎯 MARKET ALIGNMENT</div>', unsafe_allow_html=True)
    index_display = pct(n)
    if raw_index and market.get("nifty500_ltp") is not None:
        index_display = f'{fmt(market.get("nifty500_ltp"))} {"+" if num(market.get("nifty500_net_change")) >= 0 else ""}{fmt(market.get("nifty500_net_change"))} ({pct(n)})'
    st.markdown(card_grid([
        card("NIFTY 500", index_display if complete else "WAITING"),
        card("ADVANCES", advances if complete else "WAITING"),
        card("DECLINES", declines if complete else "WAITING"),
        card("A/D RATIO", fmt(ad) if complete and ad is not None else "WAITING"),
        card("POSITIVE SECTORS", positive_sectors if sector_complete else "WAITING"),
        card("NEGATIVE SECTORS", negative_sectors if sector_complete else "WAITING"),
    ]), unsafe_allow_html=True)

    st.markdown(card_grid([
        card("UNCHANGED", unchanged if complete else "WAITING"),
        card("LIVE COVERAGE", f"{evaln}/500"),
        card("SECTOR DATA", f"{sp}/500"),
        card("98% GATE", "PASS" if evaln >= MIN_DATA_COVERAGE_COUNT else "BLOCK", "buy" if evaln >= MIN_DATA_COVERAGE_COUNT else "wait"),
        card("MASTER BIAS", bias, "buy" if buy else "sell" if sell else "wait"),
    ]), unsafe_allow_html=True)

    status_ok = bool(complete and quote_count >= MIN_DATA_COVERAGE_COUNT)
    reason = str(market.get("reason") or "").replace("<", "&lt;").replace(">", "&gt;")
    status = f'<b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if status_ok else "WAIT/ERROR"} • Live snapshot {quote_count}/500 • refresh 15s'
    if not status_ok:
        status += f' • {api_status.get("message") or reason or "incomplete quote data"}'
    bg = "#092417" if status_ok else "#281313"
    border = "#28633f" if status_ok else "#6b3333"
    st.markdown(f'<div style="margin:8px 0;padding:11px 13px;background:{bg};border:1px solid {border};border-radius:11px;color:#e8eef7;font-size:13px;">{status}</div>', unsafe_allow_html=True)

    # Sector performance table intentionally removed. Sector information remains
    # available through the compact positive/negative sector cards above and is
    # still used by the master market-alignment logic.
    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">⚡ S1–S5 — TODAY</div>', unsafe_allow_html=True)

    for strategy in ["S1", "S2", "S3", "S4", "S5"]:
        tr = pd.DataFrame()
        sg = pd.DataFrame()
        for source, target in [(trades_today, "tr"), (signals_today, "sg")]:
            if source.empty:
                continue
            cols = [c for c in ["strategy", "strategy_name", "signal", "setup_type"] if c in source.columns]
            if not cols:
                continue
            mask = pd.Series(False, index=source.index)
            for c in cols:
                vals = source[c].astype(str).str.upper().str.strip()
                mask |= vals.eq(strategy) | vals.str.startswith(strategy + " ")
            if target == "tr":
                tr = source[mask]
            else:
                sg = source[mask]

        row = tr.iloc[-1] if not tr.empty else None
        signal_row = sg.iloc[-1] if not sg.empty else None
        if row is not None:
            status = str(first(row, "status", default="OPEN")).upper()
            state = "CLOSED" if status == "CLOSED" or first(row, "exit_time") not in {"", None} else "TRADE OPEN"
            cells = [("Stock", first(row, "symbol", "stock")), ("BUY / SELL", first(row, "buy_sell", "side", "signal")),
                     ("Signal Time", first(row, "trigger_entry_time", "entry_time", "market_entry_time")),
                     ("Entry", fmt(first(row, "entry", "entry_price"))), ("Stop Loss", fmt(first(row, "stop_loss"))),
                     ("Target", fmt(first(row, "target"))), ("Exit", fmt(first(row, "exit_price", "exit"))),
                     ("P&L", fmt(first(row, "pnl"))), ("Risk / Reward", fmt(first(row, "rr", "reward", "risk_reward"))),
                     ("Quantity", fmt(first(row, "quantity"))), ("Exit Reason", first(row, "exit_reason") or "—")]
        elif signal_row is not None:
            state = "SIGNAL"
            cells = [("Stock", first(signal_row, "symbol", "stock")), ("BUY / SELL", first(signal_row, "buy_sell", "side", "signal")),
                     ("Signal Time", first(signal_row, "timestamp", "entry_time", "logged_at")),
                     ("Entry", fmt(first(signal_row, "entry", "entry_price"))), ("Stop Loss", fmt(first(signal_row, "stop_loss"))),
                     ("Target", fmt(first(signal_row, "target"))), ("Exit", "—"), ("P&L", "—"),
                     ("Risk / Reward", fmt(first(signal_row, "risk_reward", "rr", "reward"))), ("Quantity", fmt(first(signal_row, "quantity"))), ("Exit Reason", "—")]
        else:
            state = "WAITING"
            cells = [("Stock", "—"), ("BUY / SELL", "—"), ("Signal Time", "—"), ("Entry", "—"), ("Stop Loss", "—"),
                     ("Target", "—"), ("Exit", "—"), ("P&L", "—"), ("Risk / Reward", "—"), ("Quantity", "—"), ("Exit Reason", "—")]

        state_color = "#67e8a5" if state == "CLOSED" else "#5ec8ff" if state == "SIGNAL" else "#ffd166" if state == "TRADE OPEN" else "#fff"
        st.markdown(strategy_card(strategy, state, state_color, cells), unsafe_allow_html=True)

    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">📥 DOWNLOAD</div>', unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV", trades_all.to_csv(index=False).encode("utf-8"), "nse_catalyst_master.csv", "text/csv", use_container_width=True, key="master_csv")

    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
    tips = ["Follow the setup, not the emotion.", "Protect capital first; profits come second.", "Wait for confirmation before entering.", "One disciplined trade is better than many emotional trades.", "Never chase a missed entry."]
    st.markdown(f'<div style="background:#101b2b;border:1px solid #294367;border-radius:13px;padding:16px;font-size:17px;font-weight:850;color:#fff;">💡 {tips[now.date().toordinal() % len(tips)]}</div>', unsafe_allow_html=True)


def render_dashboard():
    live_dashboard()


if __name__ == "__main__":
    render_dashboard()
