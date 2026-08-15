"""Candidate ranking metrics for the NIFTY 500 paper strategy."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _clean(df):
    if df is None or df.empty or "Datetime" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["Datetime"] = pd.to_datetime(out["Datetime"], errors="coerce")
    try:
        if out["Datetime"].dt.tz is None:
            out["Datetime"] = out["Datetime"].dt.tz_localize(INDIA_TZ)
        else:
            out["Datetime"] = out["Datetime"].dt.tz_convert(INDIA_TZ)
    except Exception:
        return pd.DataFrame()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["Datetime", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)


def atr_pct(intraday, period=14):
    d = _clean(intraday)
    if len(d) < period + 1 or not {"High", "Low", "Close"}.issubset(d.columns):
        return 0.0
    previous = d["Close"].shift(1)
    tr = pd.concat([(d["High"] - d["Low"]).abs(), (d["High"] - previous).abs(), (d["Low"] - previous).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(period).mean())
    close = float(d.iloc[-1]["Close"])
    return round((atr / close) * 100.0, 4) if close > 0 else 0.0


def rvol(price_data, symbol, today_intraday):
    """Time-normalized relative volume using recent daily volume as the baseline."""
    d = _clean(today_intraday)
    if d.empty or "Volume" not in d.columns:
        return 0.0
    current_volume = float(d["Volume"].fillna(0).sum())
    try:
        daily = _clean(price_data.get_daily(symbol, period="30d"))
        if daily.empty or "Volume" not in daily.columns:
            return 0.0
        avg_daily = float(daily["Volume"].tail(20).mean())
        if avg_daily <= 0:
            return 0.0
        first = d.iloc[0]["Datetime"]
        last = d.iloc[-1]["Datetime"]
        elapsed_minutes = max(1.0, (last - first).total_seconds() / 60.0 + 1.0)
        expected = avg_daily * min(1.0, elapsed_minutes / 375.0)
        return round(current_volume / expected, 3) if expected > 0 else 0.0
    except Exception:
        return 0.0


def beta(price_data, symbol, index_ticker="^CRSLDX", window=60):
    try:
        stock = _clean(price_data.get_daily(symbol, period="6mo"))
        index = _clean(price_data.get_daily(index_ticker, period="6mo"))
        if stock.empty or index.empty:
            return 0.0
        a = stock[["Datetime", "Close"]].copy(); b = index[["Datetime", "Close"]].copy()
        a["Date"] = a["Datetime"].dt.date; b["Date"] = b["Datetime"].dt.date
        a["ret"] = a["Close"].pct_change(); b["mret"] = b["Close"].pct_change()
        merged = a[["Date", "ret"]].merge(b[["Date", "mret"]], on="Date", how="inner").dropna().tail(window)
        if len(merged) < 20:
            return 0.0
        variance = float(merged["mret"].var(ddof=1))
        return round(float(merged["ret"].cov(merged["mret"]) / variance), 4) if variance > 0 else 0.0
    except Exception:
        return 0.0


def traded_value(price_data, symbol, today_intraday):
    d = _clean(today_intraday)
    if d.empty or "Volume" not in d.columns:
        return 0.0
    return round(float((d["Close"] * d["Volume"].fillna(0)).sum()), 2)


def metrics(price_data, symbol, intraday):
    d = _clean(intraday)
    return {
        "atr_pct": atr_pct(d),
        "rvol": rvol(price_data, symbol, d),
        "beta": beta(price_data, symbol),
        "traded_value": traded_value(price_data, symbol, d),
        "metrics_calculated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds"),
    }


def sort_key(row):
    return (float(row.get("atr_pct", 0) or 0), float(row.get("rvol", 0) or 0), float(row.get("beta", 0) or 0), float(row.get("traded_value", 0) or 0))
