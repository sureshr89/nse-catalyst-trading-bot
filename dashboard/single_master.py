"""NSE Catalyst production dashboard.

Compact production presentation layer for the NIFTY 500 paper-trading engine.
Consumes the shared snapshot and presents market alignment plus clean S1-S5
strategy and performance cards. Presentation only; trading logic is unchanged.
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
PALETTE = {
    "S1": ("#22c55e", "↩️", "PDH/PDL SWEEP REVERSAL"),
    "S2": ("#38bdf8", "🔁", "BREAKOUT + RETEST"),
    "S3": ("#f59e0b", "🎯", "INSIDE RANGE REVERSAL"),
    "S4": ("#a78bfa", "⚡", "INTRADAY BREAKOUT"),
    "S5": ("#f43f5e", "🚀", "PDH/PDL BREAKOUT"),
}


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
    color = {"buy": "#22c55e", "sell": "#ef4444", "wait": "#d97706"}.get(emphasis, "#334155")
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color};">{value}</div>'
        '</div>'
    )


def card_grid(items):
    return '<div class="metric-grid">' + "".join(items) + '</div>'


def strategy_card(strategy, state, state_color, cells):
    """Clean strategy card matching the compact index-card visual style."""
    accent, icon, subtitle = PALETTE.get(strategy, ("#64748b", "📊", "STRATEGY"))
    html = "".join(
        f'<div class="strategy-detail">'
        f'<div class="strategy-detail-label">{label}</div>'
        f'<div class="strategy-detail-value">{value or "—"}</div>'
        '</div>'
        for label, value in cells
    )
    return (
        f'<div class="strategy-card" style="--accent:{accent};">'
        f'<div class="strategy-top">'
        f'<div class="strategy-heading"><span class="strategy-icon">{icon}</span>'
        f'<div><div class="strategy-code" style="color:{accent};">{strategy}</div>'
        f'<div class="strategy-subtitle">{subtitle}</div></div></div>'
        f'<span class="strategy-state" style="color:{state_color};">{state}</span>'
        '</div>'
        f'<div class="strategy-details">{html}</div>'
        '</div>'
    )


def strategy_name_mask(df, strategy):
    if df.empty:
        return pd.Series(False, index=df.index)
    cols = [c for c in ["strategy", "strategy_name", "signal", "setup_type"] if c in df.columns]
    mask = pd.Series(False, index=df.index)
    for col in cols:
        vals = df[col].astype(str).str.upper().str.strip()
        mask |= vals.eq(strategy) | vals.str.startswith(strategy + " ")
    return mask


def strategy_rows(df, strategy):
    if df.empty:
        return df
    return df[strategy_name_mask(df, strategy)].copy()


def performance_stats(df, strategy):
    """Return robust strategy statistics from available trade rows."""
    rows = strategy_rows(df, strategy)
    if rows.empty:
        return {"trades": 0, "open": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl": 0.0}

    pnl = pd.to_numeric(rows.get("pnl", pd.Series(0.0, index=rows.index)), errors="coerce").fillna(0.0)
    status = rows.get("status", pd.Series("", index=rows.index)).astype(str).str.upper().str.strip()
    exit_time = rows.get("exit_time", pd.Series("", index=rows.index)).astype(str).str.strip()
    closed = status.eq("CLOSED") | exit_time.ne("").map(lambda x: x and x is not None)
    # Treat a row with an exit price/reason as closed even if status is absent.
    if "exit_price" in rows.columns:
        closed |= rows["exit_price"].astype(str).str.strip().ne("")
    open_count = int((~closed).sum())
    wins = int((closed & pnl.gt(0)).sum())
    losses = int((closed & pnl.lt(0)).sum())
    decided = wins + losses
    return {
        "trades": int(len(rows)),
        "open": open_count,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / decided * 100.0) if decided else 0.0,
        "pnl": float(pnl.sum()),
    }


def performance_card(strategy, stats, cumulative=False):
    accent, icon, subtitle = PALETTE[strategy]
    pnl = stats["pnl"]
    pnl_color = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#64748b"
    return f'''
    <div class="perf-card" style="--accent:{accent};">
      <div class="perf-head">
        <div class="perf-name"><span class="perf-icon">{icon}</span><span style="color:{accent};">{strategy}</span></div>
        <span class="perf-subtitle">{subtitle}</span>
      </div>
      <div class="perf-stats">
        <div><span>OPEN</span><b>{stats["open"]}</b></div>
        <div><span>TRADES</span><b>{stats["trades"]}</b></div>
        <div><span>WINS</span><b class="win">{stats["wins"]}</b></div>
        <div><span>LOSSES</span><b class="loss">{stats["losses"]}</b></div>
        <div><span>WIN RATE</span><b>{stats["win_rate"]:.1f}%</b></div>
        <div><span>{"CUMULATIVE P&L" if cumulative else "TODAY P&L"}</span><b style="color:{pnl_color};">₹{pnl:,.2f}</b></div>
      </div>
    </div>'''


def total_performance(stats_map):
    return {
        "trades": sum(v["trades"] for v in stats_map.values()),
        "open": sum(v["open"] for v in stats_map.values()),
        "wins": sum(v["wins"] for v in stats_map.values()),
        "losses": sum(v["losses"] for v in stats_map.values()),
        "pnl": sum(v["pnl"] for v in stats_map.values()),
    }


st.markdown("""
<style>
.stApp{background:#000!important;color:#fff!important}
.block-container{max-width:1450px;padding:.7rem .8rem 2rem}
.stCaption,.stCaption p{color:#cbd5e1!important}
.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;width:100%;margin-bottom:8px}
.metric-card{background:#f8fafc;border:1px solid #dbe7f4;border-radius:11px;padding:11px 13px;min-height:67px;box-sizing:border-box}
.metric-label{font-size:10px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.04em}
.metric-value{font-size:18px;font-weight:900;margin-top:6px;line-height:1.12}
.strategy-card,.perf-card{background:#f8fafc;border:1px solid #dbe7f4;border-radius:11px;box-sizing:border-box}
.strategy-card{padding:11px 13px;margin:9px 0}
.strategy-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
.strategy-heading{display:flex;align-items:center;gap:8px;min-width:0}
.strategy-icon{font-size:21px}.strategy-code{font-size:17px;font-weight:950;line-height:1}
.strategy-subtitle{font-size:9px;font-weight:800;color:#64748b;letter-spacing:.05em;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.strategy-state{font-size:9px;font-weight:950;background:#eef4fa;border:1px solid #dbe7f4;border-radius:999px;padding:6px 8px;white-space:nowrap}
.strategy-details{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px}
.strategy-detail{background:#eef4fa;border-radius:8px;padding:7px 8px;min-width:0}
.strategy-detail-label{font-size:8px;font-weight:850;color:#64748b;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.strategy-detail-value{font-size:12px;font-weight:900;color:#1e293b;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.performance-section{margin-top:18px}
.performance-title{font-size:20px;font-weight:950;color:#fff;margin:0 0 4px}
.performance-note{font-size:11px;color:#94a3b8;margin-bottom:9px}
.performance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
.perf-card{padding:12px;border-top:3px solid var(--accent);box-shadow:0 3px 12px rgba(0,0,0,.10)}
.perf-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}
.perf-name{font-size:18px;font-weight:950;display:flex;align-items:center;gap:7px}.perf-icon{font-size:20px}
.perf-subtitle{font-size:8px;font-weight:850;color:#64748b;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.perf-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.perf-stats div{background:#eef4fa;border-radius:8px;padding:7px 8px;min-width:0}
.perf-stats span{display:block;font-size:8px;font-weight:850;color:#64748b;letter-spacing:.04em}
.perf-stats b{display:block;font-size:13px;color:#1e293b;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.perf-stats .win{color:#16a34a}.perf-stats .loss{color:#dc2626}
.performance-total{margin-top:9px;padding:10px 12px;border-top:2px solid #cbd5e1;border-bottom:1px solid #dbe7f4;color:#e2e8f0;font-size:13px;font-weight:900;display:flex;gap:20px;flex-wrap:wrap}
.performance-total span{white-space:nowrap}.performance-total b{color:#fff}
@media (max-width:1100px){.performance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.strategy-details{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (max-width:700px){.block-container{padding:.55rem .55rem 1.5rem}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.strategy-card{padding:10px;margin:7px 0}.strategy-details{grid-template-columns:repeat(2,minmax(0,1fr))}.strategy-top{align-items:flex-start}.strategy-subtitle{max-width:180px}.performance-grid{grid-template-columns:1fr;gap:7px}.perf-card{padding:11px}.perf-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.performance-title{font-size:18px}}
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

    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">⚡ S1–S5 — TODAY</div>', unsafe_allow_html=True)
    for strategy in STRATEGIES:
        tr = strategy_rows(trades_today, strategy)
        sg = strategy_rows(signals_today, strategy)
        row = tr.iloc[-1] if not tr.empty else None
        signal_row = sg.iloc[-1] if not sg.empty else None
        if row is not None:
            status_text = str(first(row, "status", default="OPEN")).upper()
            state = "CLOSED" if status_text == "CLOSED" or first(row, "exit_time") not in {"", None} else "TRADE OPEN"
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
        state_color = "#16a34a" if state == "CLOSED" else "#0284c7" if state == "SIGNAL" else "#d97706" if state == "TRADE OPEN" else "#64748b"
        st.markdown(strategy_card(strategy, state, state_color, cells), unsafe_allow_html=True)

    today_stats = {s: performance_stats(trades_today, s) for s in STRATEGIES}
    cumulative_stats = {s: performance_stats(trades_all, s) for s in STRATEGIES}

    st.markdown('<div class="performance-section">', unsafe_allow_html=True)
    st.markdown('<div class="performance-title">📅 TODAY — ALL POSITIONS</div>', unsafe_allow_html=True)
    st.markdown('<div class="performance-note">All S1–S5 positions, wins, losses, open positions and P&amp;L for today only.</div>', unsafe_allow_html=True)
    st.markdown('<div class="performance-grid">' + ''.join(performance_card(s, today_stats[s]) for s in STRATEGIES) + '</div>', unsafe_allow_html=True)
    tt = total_performance(today_stats)
    twr = (tt["wins"] / (tt["wins"] + tt["losses"]) * 100) if tt["wins"] + tt["losses"] else 0
    tpnl_color = "#16a34a" if tt["pnl"] > 0 else "#dc2626" if tt["pnl"] < 0 else "#fff"
    st.markdown(f'<div class="performance-total"><span>OPEN <b>{tt["open"]}</b></span><span>TRADES <b>{tt["trades"]}</b></span><span>WINS <b>{tt["wins"]}</b></span><span>LOSSES <b>{tt["losses"]}</b></span><span>WIN RATE <b>{twr:.1f}%</b></span><span>P&amp;L <b style="color:{tpnl_color};">₹{tt["pnl"]:,.2f}</b></span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="performance-section">', unsafe_allow_html=True)
    st.markdown('<div class="performance-title">📈 CUMULATIVE — ALL DAYS</div>', unsafe_allow_html=True)
    st.markdown('<div class="performance-note">Complete historical performance across all available trading days.</div>', unsafe_allow_html=True)
    st.markdown('<div class="performance-grid">' + ''.join(performance_card(s, cumulative_stats[s], cumulative=True) for s in STRATEGIES) + '</div>', unsafe_allow_html=True)
    ct = total_performance(cumulative_stats)
    cwr = (ct["wins"] / (ct["wins"] + ct["losses"]) * 100) if ct["wins"] + ct["losses"] else 0
    cpnl_color = "#16a34a" if ct["pnl"] > 0 else "#dc2626" if ct["pnl"] < 0 else "#fff"
    st.markdown(f'<div class="performance-total"><span>OPEN <b>{ct["open"]}</b></span><span>TRADES <b>{ct["trades"]}</b></span><span>WINS <b>{ct["wins"]}</b></span><span>LOSSES <b>{ct["losses"]}</b></span><span>WIN RATE <b>{cwr:.1f}%</b></span><span>P&amp;L <b style="color:{cpnl_color};">₹{ct["pnl"]:,.2f}</b></span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">📥 DOWNLOAD</div>', unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV", trades_all.to_csv(index=False).encode("utf-8"), "nse_catalyst_master.csv", "text/csv", use_container_width=True, key="master_csv")

    st.markdown('<div style="font-size:20px;font-weight:950;color:#fff;margin:18px 0 9px;">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
    tips = ["Follow the setup, not the emotion.", "Protect capital first; profits come second.", "Wait for confirmation before entering.", "One disciplined trade is better than many emotional trades.", "Never chase a missed entry."]
    st.markdown(f'<div style="background:#101b2b;border:1px solid #294367;border-radius:13px;padding:16px;font-size:17px;font-weight:850;color:#fff;">💡 {tips[now.date().toordinal() % len(tips)]}</div>', unsafe_allow_html=True)


def render_dashboard():
    live_dashboard()


if __name__ == "__main__":
    render_dashboard()
