"""NSE Catalyst production dashboard.

Presentation-only dashboard for the NIFTY 500 paper-trading engine.
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
    "S5": ("#fb7185", "🚀", "PDH/PDL BREAKOUT"),
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


def metric_card(label, value, emphasis=""):
    color = {"buy": "#22c55e", "sell": "#fb7185", "wait": "#f59e0b"}.get(emphasis, "#f8fafc")
    return (
        f'<div style="background:#0d1726;border:1px solid #243752;border-radius:12px;'
        f'padding:12px 13px;min-height:76px;box-sizing:border-box;box-shadow:0 2px 8px rgba(0,0,0,.18);">'
        f'<div style="font-size:10px;font-weight:800;color:#8ea2bc;text-transform:uppercase;letter-spacing:.04em;">{label}</div>'
        f'<div style="font-size:18px;font-weight:900;color:{color};margin-top:7px;line-height:1.15;">{value}</div></div>'
    )


def metric_grid(items):
    return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;width:100%;margin-bottom:8px;">' + "".join(items) + "</div>"


def strategy_card(strategy, state, state_color, cells):
    accent, icon, subtitle = PALETTE[strategy]
    details = "".join(
        f'<div style="background:#111f32;border:1px solid #1e314b;border-radius:8px;padding:8px 9px;min-width:0;">'
        f'<div style="font-size:8px;font-weight:850;color:#8ea2bc;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:12px;font-weight:900;color:#f8fafc;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{value or "—"}</div></div>'
        for label, value in cells
    )
    return (
        f'<div style="background:#0d1726;border:1px solid #243752;border-radius:12px;border-top:3px solid {accent};padding:12px 13px;margin:9px 0;box-sizing:border-box;box-shadow:0 3px 10px rgba(0,0,0,.22);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:8px;min-width:0;"><span style="font-size:20px;">{icon}</span><div>'
        f'<div style="font-size:17px;font-weight:950;color:{accent};line-height:1;">{strategy}</div>'
        f'<div style="font-size:9px;font-weight:800;color:#8ea2bc;letter-spacing:.04em;margin-top:4px;">{subtitle}</div></div></div>'
        f'<span style="font-size:9px;font-weight:900;color:{state_color};background:#111f32;border:1px solid #2a405d;border-radius:999px;padding:6px 9px;white-space:nowrap;">{state}</span></div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:6px;">{details}</div></div>'
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
    return df[strategy_name_mask(df, strategy)].copy() if not df.empty else df


def performance_stats(df, strategy):
    rows = strategy_rows(df, strategy)
    if rows.empty:
        return {"trades": 0, "open": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl": 0.0}
    pnl = pd.to_numeric(rows["pnl"], errors="coerce").fillna(0.0) if "pnl" in rows else pd.Series(0.0, index=rows.index)
    status = rows["status"].astype(str).str.upper().str.strip() if "status" in rows else pd.Series("", index=rows.index)
    exit_time = rows["exit_time"].astype(str).str.strip() if "exit_time" in rows else pd.Series("", index=rows.index)
    closed = status.eq("CLOSED") | exit_time.ne("")
    if "exit_price" in rows:
        closed |= rows["exit_price"].astype(str).str.strip().ne("")
    open_count = int((~closed).sum())
    wins = int((closed & pnl.gt(0)).sum())
    losses = int((closed & pnl.lt(0)).sum())
    decided = wins + losses
    return {
        "trades": len(rows),
        "open": open_count,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / decided * 100 if decided else 0.0,
        "pnl": float(pnl.sum()),
    }


def performance_summary(stats_map):
    total = {
        "trades": sum(v["trades"] for v in stats_map.values()),
        "open": sum(v["open"] for v in stats_map.values()),
        "wins": sum(v["wins"] for v in stats_map.values()),
        "losses": sum(v["losses"] for v in stats_map.values()),
        "pnl": sum(v["pnl"] for v in stats_map.values()),
    }
    decided = total["wins"] + total["losses"]
    total["win_rate"] = total["wins"] / decided * 100 if decided else 0.0
    return total


def cumulative_chart_frames(trades_all):
    """Build daily and strategy cumulative P&L data from actual trade records."""
    if trades_all.empty or "pnl" not in trades_all.columns:
        return pd.DataFrame(), pd.DataFrame()
    date_col = next((c for c in ["exit_time", "entry_time", "market_entry_time", "trigger_entry_time"] if c in trades_all.columns), None)
    if not date_col:
        return pd.DataFrame(), pd.DataFrame()
    work = trades_all.copy()
    work["_pnl"] = pd.to_numeric(work["pnl"], errors="coerce").fillna(0.0)
    work["_date"] = pd.to_datetime(work[date_col], errors="coerce", utc=True).dt.tz_convert(IST).dt.date
    work = work.dropna(subset=["_date"])
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()
    daily = work.groupby("_date", as_index=True)["_pnl"].sum().sort_index().to_frame("Daily P&L")
    daily["Cumulative P&L"] = daily["Daily P&L"].cumsum()
    strategy_data = []
    for strategy in STRATEGIES:
        strategy_data.append({"Strategy": strategy, "Cumulative P&L": performance_stats(work, strategy)["pnl"]})
    return daily, pd.DataFrame(strategy_data).set_index("Strategy")


st.markdown(
    """<style>
    .stApp{background:#05080d!important;color:#f8fafc!important}
    .main,.block-container{background:#05080d!important}
    .block-container{max-width:1450px;padding:.7rem .8rem 2rem}
    .section-title{font-size:20px;font-weight:950;color:#f8fafc;margin:18px 0 9px}
    .chart-note{font-size:11px;color:#8ea2bc;margin:0 0 8px}
    @media (max-width:700px){.block-container{padding:.55rem .55rem 1.5rem}}
    </style>""",
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
            ltp = num(raw_index.get("LTP")); net = num(raw_index.get("NetChange")); prev = num(raw_index.get("PreviousClose"))
            if ltp > 0 and prev > 0:
                market.update({"nifty500_ltp": ltp, "nifty500_net_change": net, "nifty500_previous_close": prev, "nifty500_change_pct": net / prev * 100})
        dhan_ok = dhan_configured(); api_status = dhan_status()
    except Exception as exc:
        market = {"complete": False, "sector_complete": False, "evaluated": 0, "sector_priced": 0, "nifty500_change_pct": None, "ad_ratio": None, "advances": 0, "declines": 0, "unchanged": 0, "positive_sectors": 0, "negative_sectors": 0, "reason": f"{type(exc).__name__}: {exc}", "quote_rows": pd.DataFrame()}
        dhan_ok = False; api_status = {"ok": False, "message": str(exc)}; raw_index = None

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
    complete = bool(market.get("complete")); sector_complete = bool(market.get("sector_complete"))
    n = market.get("nifty500_change_pct") if complete else None; ad = market.get("ad_ratio") if complete else None
    evaln = int(market.get("evaluated", 0) or 0) if complete else 0; sp = int(market.get("sector_priced", 0) or 0) if sector_complete else 0
    advances = int(market.get("advances", 0) or 0) if complete else 0; declines = int(market.get("declines", 0) or 0) if complete else 0
    unchanged = int(market.get("unchanged", 0) or 0) if complete else 0; positive_sectors = int(market.get("positive_sectors", 0) or 0) if sector_complete else 0
    negative_sectors = int(market.get("negative_sectors", 0) or 0) if sector_complete else 0
    quote_rows = market.get("quote_rows"); quote_count = len(quote_rows) if isinstance(quote_rows, pd.DataFrame) else evaln
    buy = bool(complete and sector_complete and num(n) > 0 and positive_sectors > negative_sectors and num(ad) > 1)
    sell = bool(complete and sector_complete and num(n) < 0 and negative_sectors > positive_sectors and num(ad, 2) < 1)
    bias = "🟢 BUY" if buy else "🔴 SELL" if sell else "⚪ NO TRADE"

    st.markdown('<div style="font-size:30px;font-weight:950;color:#f8fafc;">📊 NSE Catalyst — Master Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:12px;color:#8ea2bc;margin-bottom:12px;">NIFTY 500 • PAPER TRADING ONLY • Dhan • {now.strftime("%d %b %Y %H:%M:%S")} IST • auto refresh 15s</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🎯 MARKET ALIGNMENT</div>', unsafe_allow_html=True)
    index_display = pct(n)
    if raw_index and market.get("nifty500_ltp") is not None:
        index_display = f'{fmt(market.get("nifty500_ltp"))} {"+" if num(market.get("nifty500_net_change")) >= 0 else ""}{fmt(market.get("nifty500_net_change"))} ({pct(n)})'
    st.markdown(metric_grid([
        metric_card("NIFTY 500", index_display if complete else "WAITING"), metric_card("ADVANCES", advances if complete else "WAITING"),
        metric_card("DECLINES", declines if complete else "WAITING"), metric_card("A/D RATIO", fmt(ad) if complete and ad is not None else "WAITING"),
        metric_card("POSITIVE SECTORS", positive_sectors if sector_complete else "WAITING"), metric_card("NEGATIVE SECTORS", negative_sectors if sector_complete else "WAITING")
    ]), unsafe_allow_html=True)
    st.markdown(metric_grid([
        metric_card("UNCHANGED", unchanged if complete else "WAITING"), metric_card("LIVE COVERAGE", f"{evaln}/500"),
        metric_card("SECTOR DATA", f"{sp}/500"), metric_card("98% GATE", "PASS" if evaln >= MIN_DATA_COVERAGE_COUNT else "BLOCK", "buy" if evaln >= MIN_DATA_COVERAGE_COUNT else "wait"),
        metric_card("MASTER BIAS", bias, "buy" if buy else "sell" if sell else "wait")
    ]), unsafe_allow_html=True)
    status_ok = bool(complete and quote_count >= MIN_DATA_COVERAGE_COUNT)
    reason = str(market.get("reason") or "").replace("<", "&lt;").replace(">", "&gt;")
    status = f'<b>Dhan: {"CONNECTED" if dhan_ok else "WAITING"}</b> • API: {"PASS" if status_ok else "WAIT/ERROR"} • Live snapshot {quote_count}/500 • refresh 15s'
    if not status_ok:
        status += f' • {api_status.get("message") or reason or "incomplete quote data"}'
    bg = "#052e1b" if status_ok else "#3a1115"; border = "#166534" if status_ok else "#991b1b"; text = "#86efac" if status_ok else "#fda4af"
    st.markdown(f'<div style="margin:8px 0;padding:11px 13px;background:{bg};border:1px solid {border};border-radius:11px;color:{text};font-size:13px;">{status}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">⚡ S1–S5 — TODAY</div>', unsafe_allow_html=True)
    for strategy in STRATEGIES:
        tr = strategy_rows(trades_today, strategy); sg = strategy_rows(signals_today, strategy)
        row = tr.iloc[-1] if not tr.empty else None; signal_row = sg.iloc[-1] if not sg.empty else None
        if row is not None:
            status_text = str(first(row, "status", default="OPEN")).upper()
            state = "CLOSED" if status_text == "CLOSED" or first(row, "exit_time") not in {"", None} else "TRADE OPEN"
            cells = [("Stock", first(row, "symbol", "stock")), ("BUY / SELL", first(row, "buy_sell", "side", "signal")), ("Signal Time", first(row, "trigger_entry_time", "entry_time", "market_entry_time")), ("Entry", fmt(first(row, "entry", "entry_price"))), ("Stop Loss", fmt(first(row, "stop_loss"))), ("Target", fmt(first(row, "target"))), ("Exit", fmt(first(row, "exit_price", "exit"))), ("P&L", fmt(first(row, "pnl"))), ("Risk / Reward", fmt(first(row, "rr", "reward", "risk_reward"))), ("Quantity", fmt(first(row, "quantity"))), ("Exit Reason", first(row, "exit_reason") or "—")]
        elif signal_row is not None:
            state = "SIGNAL"
            cells = [("Stock", first(signal_row, "symbol", "stock")), ("BUY / SELL", first(signal_row, "buy_sell", "side", "signal")), ("Signal Time", first(signal_row, "timestamp", "entry_time", "logged_at")), ("Entry", fmt(first(signal_row, "entry", "entry_price"))), ("Stop Loss", fmt(first(signal_row, "stop_loss"))), ("Target", fmt(first(signal_row, "target"))), ("Exit", "—"), ("P&L", "—"), ("Risk / Reward", fmt(first(signal_row, "risk_reward", "rr", "reward"))), ("Quantity", fmt(first(signal_row, "quantity"))), ("Exit Reason", "—")]
        else:
            state = "WAITING"
            cells = [("Stock", "—"), ("BUY / SELL", "—"), ("Signal Time", "—"), ("Entry", "—"), ("Stop Loss", "—"), ("Target", "—"), ("Exit", "—"), ("P&L", "—"), ("Risk / Reward", "—"), ("Quantity", "—"), ("Exit Reason", "—")]
        state_color = "#22c55e" if state == "CLOSED" else "#38bdf8" if state == "SIGNAL" else "#f59e0b" if state == "TRADE OPEN" else "#94a3b8"
        st.markdown(strategy_card(strategy, state, state_color, cells), unsafe_allow_html=True)

    today_stats = {s: performance_stats(trades_today, s) for s in STRATEGIES}
    ts = performance_summary(today_stats)
    st.markdown('<div class="section-title">📅 TODAY — ALL POSITIONS</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#8ea2bc;margin-bottom:9px;">Today overall: one combined summary across S1–S5.</div>', unsafe_allow_html=True)
    today_pnl_emphasis = "buy" if ts["pnl"] > 0 else "sell" if ts["pnl"] < 0 else ""
    st.markdown(metric_grid([
        metric_card("OPEN", ts["open"]), metric_card("TRADES", ts["trades"]), metric_card("WINS", ts["wins"], "buy"),
        metric_card("LOSSES", ts["losses"], "sell"), metric_card("WIN RATE", f'{ts["win_rate"]:.1f}%'), metric_card("P&L", f'₹{ts["pnl"]:,.2f}', today_pnl_emphasis)
    ]), unsafe_allow_html=True)

    st.markdown('<div class="section-title">📈 CUMULATIVE — ALL DAYS</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-note">Historical performance shown as charts — no strategy performance tables.</div>', unsafe_allow_html=True)
    daily_frame, strategy_frame = cumulative_chart_frames(trades_all)
    if not strategy_frame.empty:
        st.markdown('**Cumulative P&L by Strategy**')
        st.bar_chart(strategy_frame, use_container_width=True, height=260)
    if not daily_frame.empty:
        st.markdown('**Daily P&L — spikes and drawdowns**')
        st.bar_chart(daily_frame[["Daily P&L"]], use_container_width=True, height=260)
        st.markdown('**Cumulative P&L curve**')
        st.line_chart(daily_frame[["Cumulative P&L"]], use_container_width=True, height=280)
    if daily_frame.empty and strategy_frame.empty:
        st.info("No historical trade P&L data is available yet.")

    st.markdown('<div class="section-title">📥 DOWNLOAD</div>', unsafe_allow_html=True)
    st.download_button("⬇️ Download Master CSV", trades_all.to_csv(index=False).encode("utf-8"), "nse_catalyst_master.csv", "text/csv", use_container_width=True, key="master_csv")
    st.markdown('<div class="section-title">💡 DAILY TRADING TIP</div>', unsafe_allow_html=True)
    tips = ["Follow the setup, not the emotion.", "Protect capital first; profits come second.", "Wait for confirmation before entering.", "One disciplined trade is better than many emotional trades.", "Never chase a missed entry."]
    st.markdown(f'<div style="background:#0d1726;border:1px solid #243752;border-radius:12px;padding:14px;font-size:16px;font-weight:850;color:#f8fafc;">💡 {tips[now.date().toordinal() % len(tips)]}</div>', unsafe_allow_html=True)


def render_dashboard():
    live_dashboard()


if __name__ == "__main__":
    render_dashboard()
