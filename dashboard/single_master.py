"""NSE Catalyst production dashboard.

Clean presentation layer for the live NIFTY 500 paper-trading engine.
The dashboard consumes the same 15-second shared snapshot used by breadth,
sectors and S1-S5.
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


# Inline styles are intentional: they keep the cards visible even when the
# hosting Streamlit wrapper/theme strips or delays injected CSS.
def card(label, value, emphasis=""):
    value_color = {"buy": "#67e8a5", "sell": "#ff7b7b", "wait": "#ffd166"}.get(emphasis, "#ffffff")
    return (
        '<div style="background:#101b2b;border:1px solid #294367;border-radius:12px;'
        'padding:11px;min-height:68px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:10px;font-weight:900;color:#cbd5e1;text-transform:uppercase;letter-spacing:.03em;">{label}</div>'
        f'<div style="font-size:18px;font-weight:900;color:{value_color};margin-top:5px;line-height:1.15;">{value}</div>'
        '</div>'
    )


def card_grid(items):
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));'
        'gap:8px;width:100%;margin:0 0 8px 0;">'
        + "".join(items)
        + '</div>'
    )


def build_sector_rows(quote_rows):
    """Build sector returns from the finalized shared live snapshot."""
    if not isinstance(quote_rows, pd.DataFrame) or quote_rows.empty or "Symbol" not in quote_rows.columns:
        return pd.DataFrame()
    try:
        from data.sector_alignment import load_sector_map
        sector_map = load_sector_map(quote_rows[["Symbol"]].copy(), refresh=False)
    except Exception:
        return pd.DataFrame()
    if not isinstance(sector_map, pd.DataFrame) or sector_map.empty or "Sector" not in sector_map.columns:
        return pd.DataFrame()

    q = quote_rows.copy()
    q["Symbol"] = q["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
    change_col = next((c for c in ["change_pct", "ChangePct", "change_percent", "NetChangePct"] if c in q.columns), None)
    if change_col is None:
        if {"NetChange", "PreviousClose"}.issubset(q.columns):
            q["_change_pct"] = pd.to_numeric(q["NetChange"], errors="coerce") / pd.to_numeric(q["PreviousClose"], errors="coerce") * 100
            change_col = "_change_pct"
        elif {"LTP", "PreviousClose"}.issubset(q.columns):
            q["_change_pct"] = (pd.to_numeric(q["LTP"], errors="coerce") / pd.to_numeric(q["PreviousClose"], errors="coerce") - 1) * 100
            change_col = "_change_pct"
        else:
            return pd.DataFrame()

    q[change_col] = pd.to_numeric(q[change_col], errors="coerce")
    sm = sector_map[["Symbol", "Sector"]].copy()
    sm["Symbol"] = sm["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
    merged = sm.merge(q[["Symbol", change_col]], on="Symbol", how="left").dropna(subset=[change_col])
    if merged.empty:
        return pd.DataFrame()

    grouped = merged.groupby("Sector", sort=True)[change_col].agg(["mean", "count"]).reset_index()
    grouped = grouped.rename(columns={"mean": "Change %", "count": "Stocks"})
    grouped["Status"] = grouped["Change %"].map(lambda x: "POSITIVE" if x > 0 else "NEGATIVE" if x < 0 else "UNCHANGED")
    return grouped.sort_values("Change %", ascending=False).reset_index(drop=True)


st.markdown(
    """
<style>
.stApp{background:#000!important;color:#fff!important}
.block-container{max-width:1450px;padding:.7rem .8rem 2rem}
.title{font-size:clamp(1.55rem,4vw,2.4rem);font-weight:900;color:#fff}
.sub{font-size:.75rem;color:#d5dbe5;margin-bottom:10px}
.sec{font-size:1.08rem;font-weight:900;margin:16px 0 8px;color:#fff}
.status{margin:8px 0;padding:10px 12px;background:#101b2b;border:1px solid #294367;border-radius:11px;color:#e8eef7;font-size:.76rem}
.strategy{background:#0b1422;border:1px solid #294367;border-radius:12px;padding:10px;margin:8px 0}
.strategy-title{font-weight:900;font-size:.9rem;margin-bottom:7px;color:#fff}
.state{float:right;font-weight:900;font-size:.67rem;padding:4px 7px;border-radius:7px;background:#162943}
.trade-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px}
.trade-cell{background:#101b2b;border-radius:8px;padding:7px;min-width:0}
.trade-label{font-size:.49rem;color:#bfcbd9;text-transform:uppercase}
.trade-value{font-size:.72rem;font-weight:850;margin-top:2px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tip{background:#101b2b;border:1px solid #294367;border-radius:12px;padding:14px;font-weight:800;color:#fff}
.stCaption,.stCaption p{color:#cbd5e1!important}
</style>
""",
    unsafe_allow_html=True,
)


@st.fragment(run_every="15s")
def live_dashboard():
    now = datetime.now(IST)
    try:
        from market.nifty500_breadth import BREADTH
        from market.dhan_data import configured as dhan_configured, dhan_status, index_quote

        market = BREADTH.snapshot(force=False)
        raw_index = index_quote("NIFTY 500")
        if raw_index:
            ltp = float(raw_index.get("LTP") or 0)
            net = float(raw_index.get("NetChange") or 0)
            prev = float(raw_index.get("PreviousClose") or 0)
            if ltp > 0 and prev > 0:
                market["nifty500_ltp"] = ltp
                market["nifty500_net_change"] = net
                market["nifty500_previous_close"] = prev
                market["nifty500_change_pct"] = net / prev * 100
    except Exception as exc:
        market = {"complete": False, "sector_complete": False, "evaluated": 0, "sector_priced": 0, "nifty500_change_pct": None, "ad_ratio": None, "advances": 0, "declines": 0, "unchanged": 0, "positive_sectors": 0, "negative_sectors": 0, "reason": f"{type(exc).__name__}: {exc}", "quote_rows": pd.DataFrame()}
        dhan_ok = False
        api_status = {"ok": False, "message": str(exc)}
        raw_index = None
    else:
        dhan_ok = dhan_configured()
        api_status = dhan_status()

    trades_all = read_csv("trades.csv")
    signals_all = read_csv("signals.csv")
    today = now.date()
    trades_today = trades_all.copy()
    signals_today = signals_all.copy()

    if not trades_today.empty:
        dc = next((c for c in ["exit_time", "entry_time", "market_entry_time", "trigger_entry_time"] if c in trades_today.columns), None)
        if dc:
            d = pd.to_datetime(trades_today[dc], errors="coerce", utc=True)
            try:
                d = d.dt.tz_convert(IST)
            except Exception:
                pass
            trades_today = trades_today[d.dt.date == today]
    if not signals_today.empty:
        dc = next((c for c in ["timestamp", "entry_time", "logged_at"] if c in signals_today.columns), None)
        if dc:
            d = pd.to_datetime(signals_today[dc], errors="coerce", utc=True)
            try:
                d = d.dt.tz_convert(IST)
            except Exception:
                pass
            signals_today = signals_today[d.dt.date == today]

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
    quote_count = len(quote_rows) if isinstance(quote_rows, pd.DataFrame) else 0
    sector_rows = build_sector_rows(quote_rows) if sector_complete else pd.DataFrame()
    if not sector_rows.empty:
        positive_sectors = int((sector_rows["Change %"] > 0).sum())
        negative_sectors = int((sector_rows["Change %"] < 0).sum())

    buy = bool(complete and sector_complete and num(n) > 0 and positive_sectors > negative_sectors and num(ad) > 1)
    sell = bool(complete and sector_complete and num(n) < 0 and negative_sectors > positive_sectors and num(ad, 2) < 1)
    bias = "🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

    st.markdown('<div class="title">📊 NSE Catalyst — Master Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub">NIFTY 500 • PAPER TRADING ONLY • Dhan • {now.strftime("%d %b %Y %H:%M:%S")} IST • auto refresh 15s</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec">🎯 MARKET ALIGNMENT</div>', unsafe_allow_html=True)

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

    reason = str(market.get("reason") or "").replace("<", "&lt;").replace(">", "&gt;")
    status_ok = bool(complete and quote_count >= MIN_DATA_COVERAGE_COUNT)
    status_text = f'<b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if status_ok else "WAIT/ERROR"} • Live snapshot {quote_count}/500'
    if not complete:
        status_text += f' • breadth waiting: {reason or "market data incomplete"}'
    elif not status_ok:
        status_text += f' • Dhan: {api_status.get("message") or "incomplete quote data"}'
    status_text += " • refresh 15s"
    status_style = "background:#092417;border-color:#28633f" if status_ok else "background:#281313;border-color:#6b3333"
    st.markdown(f'<div class="status" style="{status_style}">{status_text}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">🏭 SECTOR PERFORMANCE</div>', unsafe_allow_html=True)
    if sector_complete and not sector_rows.empty:
        sector_display = sector_rows[["Sector", "Change %", "Status", "Stocks"]].copy()
        sector_display["Change %"] = sector_display["Change %"].map(lambda x: f"{x:+.2f}%")
        sector_display["Status"] = sector_display["Status"].map(lambda x: "🟢 POSITIVE" if x == "POSITIVE" else "🔴 NEGATIVE" if x == "NEGATIVE" else "⚪ UNCHANGED")
        st.dataframe(sector_display, width="stretch", hide_index=True)
    else:
        st.info("Waiting for complete NIFTY 500 constituent data.")

    st.markdown('<div class="sec">⚡ S1–S5 — TODAY</div>', unsafe_allow_html=True)
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
            stock = first(row, "symbol", "stock")
            side = first(row, "buy_sell", "side", "signal")
            signal_time = first(row, "trigger_entry_time", "entry_time", "market_entry_time")
            entry = first(row, "entry", "entry_price")
            sl = first(row, "stop_loss")
            target = first(row, "target")
            exit_price = first(row, "exit_price", "exit")
            pnl = first(row, "pnl")
            rr = first(row, "rr", "reward", "risk_reward")
            qty = first(row, "quantity")
            exit_reason = first(row, "exit_reason")
        elif signal_row is not None:
            state = "SIGNAL"
            stock = first(signal_row, "symbol", "stock")
            side = first(signal_row, "buy_sell", "side", "signal")
            signal_time = first(signal_row, "timestamp", "entry_time", "logged_at")
            entry = first(signal_row, "entry", "entry_price")
            sl = first(signal_row, "stop_loss")
            target = first(signal_row, "target")
            exit_price = pnl = ""
            rr = first(signal_row, "risk_reward", "rr", "reward")
            qty = first(signal_row, "quantity")
            exit_reason = ""
        else:
            state = "WAITING"
            stock = side = signal_time = entry = sl = target = exit_price = pnl = rr = qty = exit_reason = ""

        state_color = "#67e8a5" if state == "CLOSED" else "#5ec8ff" if state == "SIGNAL" else "#ffd166" if state == "TRADE OPEN" else "#ffffff"
        cells = [("Stock", stock), ("BUY / SELL", side), ("Signal Time", signal_time), ("Entry", fmt(entry)), ("Stop Loss", fmt(sl)), ("Target", fmt(target)), ("Exit", fmt(exit_price)), ("P&L", fmt(pnl)), ("Risk / Reward", fmt(rr)), ("Quantity", fmt(qty)), ("Exit Reason", exit_reason or "—")]
        html = "".join(f'<div class="trade-cell"><div class="trade-label">{label}</div><div class="trade-value">{value or "—"}</div></div>' for label, value in cells)
        st.markdown(f'<div class="strategy"><span class="state" style="color:{state_color}">{state}</span><div class="strategy-title">{strategy}</div><div class="trade-grid">{html}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">📥 DOWNLOAD</div>', unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV", trades_all.to_csv(index=False).encode("utf-8"), "nse_catalyst_master.csv", "text/csv", use_container_width=True, key="master_csv")

    st.markdown('<div class="sec">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
    tips = ["Follow the setup, not the emotion.", "Protect capital first; profits come second.", "Wait for confirmation before entering.", "One disciplined trade is better than many emotional trades.", "Never chase a missed entry."]
    st.markdown(f'<div class="tip">💡 {tips[now.date().toordinal() % len(tips)]}</div>', unsafe_allow_html=True)


def render_dashboard():
    live_dashboard()


if __name__ == "__main__":
    render_dashboard()
