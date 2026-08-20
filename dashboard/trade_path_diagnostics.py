"""Transparent live trade-path diagnostics for the paper-trading dashboard."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import streamlit as st

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PATH = OUT / "trade_path_diagnostics.json"


def capture(engine, cycle_result=None, error=None):
    """Record the NORMAL engine cycle without executing a second trade."""
    d = getattr(engine, "diagnostics", {}) or {}
    selected = getattr(engine, "last_signals", []) or []
    open_positions = getattr(getattr(engine, "paper_engine", None), "open_positions", {}) or {}
    rejection = d.get("rejections", {}) or {}
    coverage = str(d.get("market_data_coverage", "0/500"))
    ad_coverage = str(d.get("ad_coverage", "0/500"))
    sector_coverage = str(d.get("sector_priced", "0/500"))

    market_snapshot = d.get("market_snapshot")
    if market_snapshot in {"PASS", "BLOCKED"}:
        market_status = market_snapshot
    else:
        market_status = "PASS" if coverage == "500/500" and ad_coverage == "500/500" and sector_coverage == "500/500" else "BLOCKED"

    gate = d.get("market_gate")
    if gate not in {"BUY", "SELL", "NO_ALIGNMENT"}:
        gate = "BUY" if d.get("buy_alignment") else "SELL" if d.get("sell_alignment") else "NO_ALIGNMENT"

    generated = int(d.get("signals_generated_total", len(cycle_result or selected)) or 0)
    selected_count = int(d.get("final_signals", len(selected)) or 0)
    candidates = d.get("signals_by_strategy") or {s: 0 for s in ["S1", "S2", "S3", "S4", "S5"]}

    payload = {
        "timestamp": datetime.now(IST).isoformat(timespec="seconds"),
        "worker": "ERROR" if error else "PASS",
        "worker_status": "ERROR" if error else "PASS",
        "market_snapshot": market_status,
        "market_gate": gate,
        "strategy_market_gate": d.get("strategy_market_gate", "BLOCKED"),
        "stocks_scanned": d.get("stocks_scanned", 0),
        "strategy_reference_coverage": d.get("strategy_reference_coverage", "0/500"),
        "stock_coverage": coverage,
        "ad_coverage": ad_coverage,
        "sector_coverage": sector_coverage,
        "ad_ratio": d.get("ad_ratio"),
        "advances": d.get("ad_advances", 0),
        "declines": d.get("ad_declines", 0),
        "nifty500_change_pct": d.get("nifty500_change_pct"),
        "sector_change_pct": d.get("sector_change_pct"),
        "strategy_candidates": candidates,
        "signals_generated_total": generated,
        "signals_generated": generated,
        "signals_selected": selected_count,
        "final_signals": selected_count,
        "execution_attempts": len(selected),
        "opened_trades": len(open_positions),
        "execution_opened": len(open_positions),
        "execution_rejections": rejection,
        "execution_rejected": len(rejection) if isinstance(rejection, dict) else 0,
        "open_positions": list(open_positions.keys()) if isinstance(open_positions, dict) else [],
        "cycle_result_count": len(cycle_result or []),
        "error": f"{type(error).__name__}: {error}" if error else None,
    }
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return payload


def read():
    try:
        return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else None
    except Exception:
        return None


def _badge(value, good=None):
    value = str(value)
    cls = "good" if good is True else "bad" if good is False else "neutral"
    return f'<span class="tp-badge {cls}">{value}</span>'


def render():
    data = read()
    if not data:
        st.info("Waiting for the first paper-trading engine cycle…")
        return

    candidates = data.get("strategy_candidates") or {}
    generated = int(data.get("signals_generated_total", data.get("signals_generated", 0)) or 0)
    selected = int(data.get("signals_selected", data.get("final_signals", 0)) or 0)
    opened = int(data.get("opened_trades", data.get("execution_opened", 0)) or 0)
    gate = data.get("market_gate", "NO_ALIGNMENT")
    market = data.get("market_snapshot", "BLOCKED")
    strategy_gate = data.get("strategy_market_gate", "BLOCKED")
    rejections = data.get("execution_rejections") or {}

    st.markdown("""
    <style>
    .tp-wrap{margin:14px 0 18px 0;font-family:Arial,sans-serif}
    .tp-title{font-size:22px;font-weight:700;color:#f5f7fa;margin:0 0 4px 0}
    .tp-sub{font-size:12px;color:#8fa3b8;margin-bottom:12px}
    .tp-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:10px}
    .tp-card{background:#0b1726;border:1px solid #203c5c;border-radius:7px;padding:9px 11px;min-height:54px;box-sizing:border-box}
    .tp-label{font-size:10px;color:#8fa3b8;text-transform:uppercase;letter-spacing:.35px;margin-bottom:5px}
    .tp-value{font-size:14px;font-weight:700;color:#f5f7fa;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tp-strategy-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:8px 0 10px}
    .tp-strategy{background:#0b1726;border:1px solid #29496c;border-radius:7px;padding:8px 10px;text-align:center}
    .tp-strategy .tp-label{margin-bottom:4px}.tp-strategy .tp-value{font-size:20px}
    .tp-note{background:#0b2238;border:1px solid #173b5c;border-radius:7px;padding:9px 12px;color:#9bc8f5;font-size:12px;margin-top:8px}
    .tp-badge{display:inline-block;padding:3px 7px;border-radius:10px;font-size:11px;font-weight:700}
    .tp-badge.good{background:#0d2b1a;color:#5ee38b}.tp-badge.bad{background:#321317;color:#ff7782}.tp-badge.neutral{background:#172538;color:#b8c7d9}
    @media(max-width:900px){.tp-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.tp-strategy-grid{grid-template-columns:repeat(5,minmax(70px,1fr));overflow-x:auto}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="tp-wrap">
      <div class="tp-title">🔎 Trade Path — Live Diagnostic</div>
      <div class="tp-sub">Same engine cycle • paper trading only • refreshed every 15 seconds</div>
      <div class="tp-grid">
        <div class="tp-card"><div class="tp-label">Worker</div><div class="tp-value">{_badge(data.get('worker','PASS'), data.get('worker','PASS') == 'PASS')}</div></div>
        <div class="tp-card"><div class="tp-label">Market snapshot</div><div class="tp-value">{_badge(market, market == 'PASS')}</div></div>
        <div class="tp-card"><div class="tp-label">Market gate</div><div class="tp-value">{_badge(gate, gate in {'BUY','SELL'})}</div></div>
        <div class="tp-card"><div class="tp-label">Strategy gate</div><div class="tp-value">{_badge(strategy_gate, strategy_gate == 'PASS')}</div></div>
        <div class="tp-card"><div class="tp-label">Stocks</div><div class="tp-value">{data.get('stock_coverage','0/500')}</div></div>
        <div class="tp-card"><div class="tp-label">A / D</div><div class="tp-value">{data.get('ad_coverage','0/500')} • {data.get('ad_ratio','—')}</div></div>
        <div class="tp-card"><div class="tp-label">Sectors</div><div class="tp-value">{data.get('sector_coverage','0/500')}</div></div>
        <div class="tp-card"><div class="tp-label">NIFTY 500</div><div class="tp-value">{data.get('nifty500_change_pct','—')}%</div></div>
      </div>
      <div class="tp-strategy-grid">
        {''.join(f'<div class="tp-strategy"><div class="tp-label">{s}</div><div class="tp-value">{int(candidates.get(s,0) or 0)}</div></div>' for s in ['S1','S2','S3','S4','S5'])}
      </div>
      <div class="tp-grid">
        <div class="tp-card"><div class="tp-label">Signals generated</div><div class="tp-value">{generated}</div></div>
        <div class="tp-card"><div class="tp-label">Signals selected</div><div class="tp-value">{selected}</div></div>
        <div class="tp-card"><div class="tp-label">Execution attempts</div><div class="tp-value">{int(data.get('execution_attempts',0) or 0)}</div></div>
        <div class="tp-card"><div class="tp-label">Paper trades opened</div><div class="tp-value">{opened}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if generated == 0:
        if gate == "NO_ALIGNMENT":
            msg = "No trade: the master market gate has no BUY/SELL alignment yet. This is a market-condition block, not an execution failure."
        elif rejections:
            msg = "No trade: the strategy scan returned no eligible signal. The current blocking conditions are available below."
        else:
            msg = "No trade: market alignment is present, but none of S1–S5 produced an eligible setup on this cycle. The bot is not forcing a trade."
        st.markdown(f'<div class="tp-note">ℹ️ {msg}</div>', unsafe_allow_html=True)
    elif opened == 0:
        st.markdown('<div class="tp-note">⚠️ Signal(s) reached selection, but no paper position was opened. Check execution rejection details.</div>', unsafe_allow_html=True)
    else:
        st.success(f"Paper execution path is active: {opened} trade(s) currently open.")

    if rejections:
        with st.expander("Current blocking / rejection details", expanded=False):
            st.json(rejections)
    if data.get("error"):
        st.error(str(data["error"]))
