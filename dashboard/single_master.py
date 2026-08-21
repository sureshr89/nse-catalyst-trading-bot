"""NSE Catalyst production dashboard.

Presentation-only dashboard for the NIFTY 500 paper-trading engine.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
import pandas as pd
import streamlit as st
from config.settings import MIN_DATA_COVERAGE_COUNT

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
IST = ZoneInfo("Asia/Kolkata")
STRATEGIES = ["S1", "S2", "S3", "S4", "S5"]
PALETTE = {
    "S1": ("#22c55e", "↩️", "PDH/PDL SWEEP + OPEN RECLAIM"),
    "S2": ("#38bdf8", "🔁", "PDH/PDL BREAKOUT + RETEST"),
    "S3": ("#f59e0b", "🎯", "OPPOSITE PDH/PDL SWEEP + OPEN REVERSAL"),
    "S4": ("#a78bfa", "⚡", "INTRADAY HIGH/LOW BREAKOUT"),
    "S5": ("#fb7185", "🚀", "DIRECT PDH/PDL BREAKOUT"),
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
        f'<div style="font-size:8px;font-weight:850;color:#8ea2bc;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{escape(str(label))}</div>'
        f'<div style="font-size:12px;font-weight:900;color:#f8fafc;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{escape(str(value or "—"))}</div></div>'
        for label, value in cells
    )
    return (
        f'<div style="background:#0d1726;border:1px solid #243752;border-radius:12px;border-top:3px solid {accent};padding:12px 13px;margin:9px 0;box-sizing:border-box;box-shadow:0 3px 10px rgba(0,0,0,.22);">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:8px;min-width:0;"><span style="font-size:20px;">{icon}</span><div>'
        f'<div style="font-size:17px;font-weight:950;color:{accent};line-height:1;">{strategy}</div>'
        f'<div style="font-size:9px;font-weight:800;color:#8ea2bc;letter-spacing:.04em;margin-top:4px;">{subtitle}</div></div></div>'
        f'<span style="font-size:9px;font-weight:900;color:{state_color};background:#111f32;border:1px solid #2a405d;border-radius:999px;padding:6px 9px;white-space:nowrap;">{escape(str(state))}</span></div>'
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


def news_table(row, symbol, side):
    """Render the exact news rationale stored with a selected signal/trade."""
    values = {}
    if row is not None:
        for key in ["news_sentiment", "news_strength_score", "news_priority_rank", "news_headline", "news_published", "news_source", "news_headline_count", "sector"]:
            values[key] = first(row, key, default="")
    try:
        from market.news_ranker import snapshot as news_snapshot
        cached = news_snapshot().get(str(symbol).upper().strip(), {}) if symbol else {}
        if not values.get("news_headline") and cached:
            score = num(cached.get("score"))
            headlines = cached.get("headlines") or []
            latest = max(headlines, key=lambda h: str(h.get("published", ""))) if headlines else {}
            values.update({
                "news_sentiment": "POSITIVE" if score > 0 else "NEGATIVE" if score < 0 else "NEUTRAL",
                "news_strength_score": abs(score),
                "news_headline": latest.get("title", ""),
                "news_published": latest.get("published", ""),
                "news_source": latest.get("source", ""),
                "news_headline_count": len(headlines),
            })
    except Exception:
        pass
    if not values.get("news_headline"):
        return '<div style="margin:0 0 12px;padding:10px 12px;background:#0b1320;border:1px dashed #294367;border-radius:10px;color:#8ea2bc;font-size:12px;">📰 News rationale: no cached matching headline available yet for this selection.</div>'
    sentiment = str(values.get("news_sentiment") or "NEUTRAL").upper()
    sentiment_color = "#22c55e" if sentiment == "POSITIVE" else "#fb7185" if sentiment == "NEGATIVE" else "#f59e0b"
    cells = [
        ("Sentiment", sentiment, sentiment_color),
        ("Strength", fmt(values.get("news_strength_score")), "#f8fafc"),
        ("Priority", f'#{values.get("news_priority_rank")}' if values.get("news_priority_rank") not in {"", None} else "—", "#38bdf8"),
        ("Headlines", values.get("news_headline_count") or "1", "#f8fafc"),
        ("Sector", values.get("sector") or "—", "#f8fafc"),
        ("Side", side or "—", "#22c55e" if str(side).upper() == "BUY" else "#fb7185"),
    ]
    header = "".join(f'<th style="padding:7px 8px;text-align:left;color:#8ea2bc;font-size:9px;text-transform:uppercase;">{escape(str(k))}</th>' for k, _, _ in cells)
    body = "".join(f'<td style="padding:7px 8px;color:{c};font-size:12px;font-weight:850;">{escape(str(v))}</td>' for _, v, c in cells)
    headline = escape(str(values.get("news_headline") or "—"))
    source = escape(str(values.get("news_source") or "—"))
    published = escape(str(values.get("news_published") or "—"))
    return (
        '<div style="margin:0 0 12px;padding:10px 12px;background:#0b1320;border:1px solid #294367;border-radius:10px;">'
        '<div style="font-size:12px;font-weight:900;color:#f8fafc;margin-bottom:7px;">📰 WHY SELECTED — NEWS</div>'
        f'<div style="font-size:13px;font-weight:800;color:#e2e8f0;line-height:1.35;margin-bottom:7px;">{headline}</div>'
        f'<div style="font-size:10px;color:#8ea2bc;margin-bottom:8px;">Source: {source} • Published: {published}</div>'
        f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{header}</tr></thead><tbody><tr>{body}</tr></tbody></table>'
        '</div>'
    )


def build_master_download(trades_all, signals_all):
    """Create one research-ready cumulative CSV with trade, news, gap and daily context."""
    trades = trades_all.copy() if not trades_all.empty else pd.DataFrame()
    signals = signals_all.copy() if not signals_all.empty else pd.DataFrame()
    if not trades.empty:
        trades["RecordType"] = "TRADE"
    if not signals.empty:
        signals["RecordType"] = "SIGNAL"
        if "trade_id" in signals.columns and "trade_id" in trades.columns:
            traded_ids = set(trades["trade_id"].astype(str).str.strip())
            signals = signals[~signals["trade_id"].astype(str).str.strip().isin(traded_ids)].copy()
    parts = [x for x in [trades, signals] if not x.empty]
    base = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if base.empty:
        return base
    date_col = next((c for c in ["TradeDate", "entry_time", "timestamp", "exit_time"] if c in base.columns), None)
    if date_col:
        base["TradeDate"] = pd.to_datetime(base[date_col], errors="coerce", utc=True).dt.tz_convert(IST).dt.strftime("%Y-%m-%d")
    gap = read_csv("MASTER_DAILY_STOCK_DATA.csv")
    if gap.empty:
        gap = read_csv("gap_analysis.csv")
    if not gap.empty and "Symbol" in gap.columns:
        gap = gap.copy()
        if "TradeDate" not in gap.columns:
            gap["TradeDate"] = ""
        keep = [c for c in gap.columns if c not in base.columns or c in {"Symbol", "TradeDate"}]
        gap = gap[keep].copy()
        if "Symbol" in base.columns:
            base["_SymbolKey"] = base["Symbol"].astype(str).str.upper().str.strip()
            gap["_SymbolKey"] = gap["Symbol"].astype(str).str.upper().str.strip()
            if "TradeDate" in gap.columns:
                base = base.merge(gap.drop_duplicates(["_SymbolKey", "TradeDate"]), on=["_SymbolKey", "TradeDate"], how="left", suffixes=("", "_gap"))
            base.drop(columns=["_SymbolKey"], inplace=True, errors="ignore")
    return base


def render_dashboard():
    now = datetime.now(IST)
    trades_all = read_csv("trades.csv")
    signals_all = read_csv("signals.csv")
    diagnostics = read_csv("trade_path_diagnostics.csv")

    st.markdown("# 📊 NSE Catalyst — Master Dashboard")
    st.caption(f"NIFTY 500 • PAPER TRADING ONLY • {now.strftime('%d %b %Y %H:%M:%S IST')} • live cycle / strategy contract aligned")

    if diagnostics is not None and not diagnostics.empty:
        st.caption("Latest persisted trade-path diagnostic is available in outputs/trade_path_diagnostics.csv.")

    # Live coverage comes from the same engine diagnostic snapshot, not a separate
    # dashboard-side data source. This prevents the UI from implying readiness
    # when the production market gate is blocked.
    diag_json = OUTPUTS / "master_diagnostics.json"
    diag = {}
    try:
        import json
        if diag_json.exists():
            diag = json.loads(diag_json.read_text(encoding="utf-8"))
    except Exception:
        diag = {}

    coverage = str(diag.get("market_data_coverage", "0/500"))
    ad_coverage = str(diag.get("ad_coverage", "0/500"))
    sector_coverage = str(diag.get("sector_priced", "0/500"))
    gate = str(diag.get("buy_alignment") and "BUY" or diag.get("sell_alignment") and "SELL" or "NO_ALIGNMENT")
    trade_ready = bool(diag.get("trade_ready"))

    st.markdown("### 🎯 Master Market Alignment")
    st.markdown(metric_grid([
        metric_card("NIFTY 500", pct(diag.get("nifty500_change_pct"))),
        metric_card("A / D RATIO", fmt(diag.get("ad_ratio"))),
        metric_card("BREADTH", coverage),
        metric_card("SECTOR DATA", sector_coverage),
        metric_card("MASTER GATE", gate, "buy" if gate == "BUY" else "sell" if gate == "SELL" else "wait"),
        metric_card("TRADE READY", "YES" if trade_ready else "NO", "buy" if trade_ready else "wait"),
    ]), unsafe_allow_html=True)

    # Keep all strategy labels sourced from the canonical dashboard palette above.
    for sid in STRATEGIES:
        rows = strategy_rows(signals_all, sid)
        latest = rows.iloc[-1] if not rows.empty else None
        if latest is None:
            state = "WAITING"
            color = "#f59e0b"
            cells = [("Signals", 0), ("Side", "—"), ("Entry", "—"), ("SL", "—"), ("Target", "—"), ("News", "—")]
        else:
            side = first(latest, "side", "signal", default="—")
            cells = [
                ("Signals", len(rows)),
                ("Side", side),
                ("Entry", fmt(first(latest, "entry", default=""))),
                ("SL", fmt(first(latest, "stop_loss", "sl", default=""))),
                ("Target", fmt(first(latest, "target", default=""))),
                ("News", first(latest, "news_sentiment", default="—")),
            ]
            state = "BUY" if str(side).upper() == "BUY" else "SELL" if str(side).upper() == "SELL" else "READY"
            color = "#22c55e" if state == "BUY" else "#fb7185" if state == "SELL" else "#38bdf8"
        st.markdown(strategy_card(sid, state, color, cells), unsafe_allow_html=True)

    st.markdown("### 📈 Actual Paper Performance")
    stats = {sid: performance_stats(trades_all, sid) for sid in STRATEGIES}
    total = performance_summary(stats)
    st.markdown(metric_grid([
        metric_card("TRADES", total["trades"]),
        metric_card("WINS", total["wins"], "buy"),
        metric_card("LOSSES", total["losses"], "sell"),
        metric_card("WIN RATE", f'{total["win_rate"]:.1f}%'),
        metric_card("P&L", f'₹{total["pnl"]:,.2f}', "buy" if total["pnl"] >= 0 else "sell"),
    ]), unsafe_allow_html=True)

    st.markdown("### 📰 News-backed selection")
    if not signals_all.empty:
        shown = [c for c in [
            "entry_time", "strategy", "symbol", "side", "news_sentiment", "news_strength_score",
            "news_priority_rank", "news_headline", "news_source", "news_published", "sector",
        ] if c in signals_all.columns]
        if shown:
            st.dataframe(signals_all[shown].tail(20), use_container_width=True, hide_index=True)
        else:
            st.info("Signals exist, but no persisted news fields are available in the current ledger.")
    else:
        st.info("No persisted S1–S5 signals yet.")

    st.markdown("### 🧪 Research / Diagnostics")
    with st.expander("Trade path diagnostics", expanded=False):
        try:
            from dashboard.trade_path_diagnostics import render as render_trade_path
            render_trade_path()
        except Exception as exc:
            st.error(f"Trade-path diagnostics unavailable: {type(exc).__name__}: {exc}")

    with st.expander("S1–S5 strategy lab", expanded=False):
        try:
            from dashboard.strategy_lab import render_strategy_lab
            render_strategy_lab()
        except Exception as exc:
            st.error(f"Strategy lab unavailable: {type(exc).__name__}: {exc}")

    master = build_master_download(trades_all, signals_all)
    if not master.empty:
        st.download_button(
            "⬇️ Download Master Research CSV",
            master.to_csv(index=False).encode(),
            "master_research.csv",
            "text/csv",
        )

    st.caption(
        f"Coverage gate requires at least {MIN_DATA_COVERAGE_COUNT}/500 fresh quotes. "
        "The dashboard never substitutes partial data, current-session OHLC, or diagnostic estimates for the production market gate."
    )
