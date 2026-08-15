"""Immediate paper-entry market-price helper."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

INDIA_TZ=ZoneInfo("Asia/Kolkata")

def get_current_market_price(symbol, timeout=10):
    """Return the freshest available 1-minute market price for paper entry."""
    ticker=str(symbol).strip().upper(); ticker=ticker if ticker.startswith("^") or ticker.endswith(".NS") else f"{ticker}.NS"
    try:
        raw=yf.download(tickers=ticker,period="1d",interval="1m",auto_adjust=False,progress=False,threads=False,prepost=False,timeout=timeout)
        if raw is None or raw.empty:return None
        if isinstance(raw.columns,pd.MultiIndex):
            raw.columns=[c[0] if isinstance(c,tuple) else c for c in raw.columns]
        raw=raw.reset_index()
        rename={}
        for c in raw.columns:
            low=str(c).strip().lower()
            if low in {"datetime","date"}:rename[c]="Datetime"
            elif low=="close":rename[c]="Close"
        raw=raw.rename(columns=rename)
        if "Datetime" not in raw.columns or "Close" not in raw.columns:return None
        raw["Datetime"]=pd.to_datetime(raw["Datetime"],errors="coerce")
        if raw["Datetime"].dt.tz is None:raw["Datetime"]=raw["Datetime"].dt.tz_localize(INDIA_TZ)
        else:raw["Datetime"]=raw["Datetime"].dt.tz_convert(INDIA_TZ)
        raw["Close"]=pd.to_numeric(raw["Close"],errors="coerce"); raw=raw.dropna(subset=["Datetime","Close"])
        if raw.empty:return None
        row=raw.iloc[-1]; stamp=row["Datetime"]; age=(datetime.now(INDIA_TZ)-stamp.to_pydatetime()).total_seconds()
        if age<0 or age>120:return None
        return {"Close":float(row["Close"]),"Datetime":stamp.to_pydatetime(),"price_source":"fresh_1m_market_price"}
    except Exception as error:
        print(f"Current market price failed for {symbol}: {type(error).__name__}: {error}"); return None
