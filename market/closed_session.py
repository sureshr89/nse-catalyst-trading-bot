"""Independent post-market NIFTY 500 closed-session snapshot.
Runs separately from live-market logic and persists the completed session locally.
"""
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd

from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.dhan_data import configured, map_nifty500, market_quote, index_quote, dhan_status

IST = ZoneInfo("Asia/Kolkata")
CLOSE = dt_time(15, 30)
ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "closed_sessions"
STORE.mkdir(parents=True, exist_ok=True)


def _session_date():
    now = datetime.now(IST)
    return now.date()


def _file(d):
    return STORE / f"nifty500_closed_{d.isoformat()}.csv"


def _summary_file(d):
    return STORE / f"nifty500_closed_{d.isoformat()}.json"


def load_saved(date=None):
    d = date or _session_date()
    p = _file(d)
    if not p.exists():
        return pd.DataFrame(), {}
    try:
        df = pd.read_csv(p)
        summary = json.loads(_summary_file(d).read_text()) if _summary_file(d).exists() else {}
        return df, summary
    except Exception:
        return pd.DataFrame(), {}


def latest_saved_before(date=None):
    d = date or _session_date()
    files = sorted(STORE.glob("nifty500_closed_*.csv"))
    candidates = []
    for p in files:
        try:
            x = p.stem.replace("nifty500_closed_", "")
            if x < d.isoformat(): candidates.append((x, p))
        except Exception:
            pass
    if not candidates: return pd.DataFrame(), {}
    return load_saved(datetime.fromisoformat(candidates[-1][0]).date())


def build_closed_snapshot(force=False):
    now = datetime.now(IST)
    # Before 15:30 there is no completed current session. Use the latest saved session.
    if now.time() < CLOSE:
        df, summary = latest_saved_before(now.date())
        if not df.empty:
            return df, summary
        return pd.DataFrame(), {"complete": False, "reason": "No saved completed NSE session yet"}

    existing, summary = load_saved(now.date())
    if not force and not existing.empty and len(existing) >= 500:
        return existing, summary
    if not configured():
        return pd.DataFrame(), {"complete": False, "reason": "Dhan credentials not configured", "dhan_status": dhan_status()}

    u = StockUniverse().get_dataframe(refresh=False)
    if u is None or u.empty or "Symbol" not in u.columns:
        u = StockUniverse().get_dataframe(refresh=True)
    if u is None or u.empty:
        return pd.DataFrame(), {"complete": False, "reason": "NIFTY 500 universe unavailable"}
    u = u.copy()
    u["Symbol"] = u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS", "", regex=False)
    u = u.drop_duplicates("Symbol").head(500)
    if len(u) != 500:
        return pd.DataFrame(), {"complete": False, "reason": f"NIFTY 500 universe only {len(u)}/500"}

    mapping = map_nifty500(u["Symbol"].tolist())
    if len(mapping) != 500:
        return pd.DataFrame(), {"complete": False, "reason": f"Dhan security mapping only {len(mapping)}/500", "dhan_status": dhan_status()}

    q = market_quote(mapping, cache_seconds=0)
    if q.empty:
        return pd.DataFrame(), {"complete": False, "reason": "Dhan returned no closed-session quotes", "dhan_status": dhan_status()}

    q["TodayClose"] = pd.to_numeric(q["TodayClose"], errors="coerce")
    q["PreviousClose"] = pd.to_numeric(q["PreviousClose"], errors="coerce")
    q = q.dropna(subset=["TodayClose", "PreviousClose"])
    q = q[(q["TodayClose"] > 0) & (q["PreviousClose"] > 0)].copy()
    if q.empty:
        return pd.DataFrame(), {"complete": False, "reason": "Dhan quotes contained no usable closes", "dhan_status": dhan_status()}

    q["Close"] = q["TodayClose"]
    q["ChangePct"] = (q["Close"] - q["PreviousClose"]) / q["PreviousClose"] * 100
    advances = int((q.ChangePct > 0).sum()); declines = int((q.ChangePct < 0).sum()); unchanged = int((q.ChangePct == 0).sum())
    ad = float(advances / declines) if declines else None

    try:
        sm = load_sector_map(u, refresh=False)
        sector = calculate_sector_alignment(q[["Symbol", "ChangePct"]].rename(columns={"ChangePct":"change_pct"}), sm, "change_pct")
    except Exception as exc:
        sector = {"available": False, "alignment_pct": None, "mapped": 0, "priced": 0, "sectors": 0, "positive_sectors": 0, "negative_sectors": 0, "coverage": "0/500", "error": str(exc)}

    idx = index_quote("NIFTY 500")
    summary = {
        "complete": len(q) == 500,
        "session_date": now.date().isoformat(),
        "market_close": "15:30 IST",
        "nifty500_close": (idx or {}).get("Close"),
        "nifty500_previous_close": (idx or {}).get("PreviousClose"),
        "nifty500_change_pct": (idx or {}).get("NetChange"),
        "advances": advances, "declines": declines, "unchanged": unchanged,
        "ad_ratio": ad,
        "sector_alignment_pct": sector.get("alignment_pct"),
        "positive_sectors": sector.get("positive_sectors", 0), "negative_sectors": sector.get("negative_sectors", 0),
        "sector_coverage": sector.get("coverage", "0/500"), "coverage": f"{len(q)}/500",
        "source": "Dhan completed-session quote/OHLC", "saved_at": now.isoformat(),
        "dhan_status": dhan_status(),
    }
    out = q[[c for c in ["Symbol","SecurityId","Close","PreviousClose","TodayOpen","TodayHigh","TodayLow","Volume","ChangePct"] if c in q.columns]].copy()
    out.to_csv(_file(now.date()), index=False)
    _summary_file(now.date()).write_text(json.dumps(summary, indent=2, default=str))
    return out, summary
