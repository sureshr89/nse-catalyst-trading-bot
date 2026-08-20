"""NIFTY 500 sector mapping and integrity-checked sector alignment."""
from pathlib import Path
import pandas as pd
from config.settings import MIN_DATA_COVERAGE_COUNT

CACHE=Path("data/nifty500_sector_map.csv")
REQUIRED=500

def _norm(x): return str(x).upper().strip().replace(".NS","")

def build_sector_map(universe):
    if universe is None or universe.empty or "Symbol" not in universe.columns: raise ValueError("NIFTY 500 universe unavailable")
    sector_col=next((c for c in ["Sector","Industry","Industry Name"] if c in universe.columns),None)
    if sector_col is None: raise ValueError("NIFTY 500 sector/industry column unavailable")
    out=universe[["Symbol",sector_col]].rename(columns={sector_col:"Sector"}).copy()
    out["Symbol"]=out["Symbol"].map(_norm); out["Sector"]=out["Sector"].astype(str).str.strip()
    out=out.replace({"Sector":{"":pd.NA,"UNKNOWN":pd.NA,"NAN":pd.NA,"NONE":pd.NA}}).dropna(subset=["Symbol","Sector"]).drop_duplicates("Symbol")
    if len(out)<REQUIRED: raise ValueError(f"Sector mapping incomplete: {len(out)}/{REQUIRED}")
    CACHE.parent.mkdir(parents=True,exist_ok=True); out.to_csv(CACHE,index=False); return out

def load_sector_map(universe,refresh=False):
    expected=set(_norm(s) for s in universe.get("Symbol",[])) if universe is not None and not universe.empty else set()
    if not refresh and CACHE.exists():
        try:
            cached=pd.read_csv(CACHE); cached["Symbol"]=cached["Symbol"].map(_norm); actual=set(cached["Symbol"])
            if len(cached)>=REQUIRED and {"Symbol","Sector"}.issubset(cached.columns) and expected and expected.issubset(actual): return cached.drop_duplicates("Symbol")
        except Exception: pass
    return build_sector_map(universe)

def calculate_sector_alignment(prices,sector_map,price_col="change_pct"):
    empty={"available":False,"alignment_pct":None,"mapped":0,"priced":0,"sectors":0,"positive_sectors":0,"negative_sectors":0,"unchanged_sectors":0,"coverage":"0/500"}
    if prices is None or prices.empty or sector_map is None or sector_map.empty: return empty
    if not {"Symbol","Sector"}.issubset(sector_map.columns) or "Symbol" not in prices.columns or price_col not in prices.columns: return empty
    p=prices[["Symbol",price_col]].copy(); p["Symbol"]=p["Symbol"].map(_norm); p[price_col]=pd.to_numeric(p[price_col],errors="coerce")
    m=sector_map[["Symbol","Sector"]].copy(); m["Symbol"]=m["Symbol"].map(_norm); m=m.drop_duplicates("Symbol")
    merged=m.merge(p,on="Symbol",how="left").dropna(subset=["Sector",price_col])
    mapped=int(m["Symbol"].nunique()); priced=int(merged["Symbol"].nunique())
    if priced<MIN_DATA_COVERAGE_COUNT: return {**empty,"mapped":mapped,"priced":priced,"coverage":f"{priced}/500"}
    sector_returns=merged.groupby("Sector",sort=True)[price_col].mean()
    total=int(len(sector_returns)); pos=int((sector_returns>0).sum()); neg=int((sector_returns<0).sum()); unchanged=int((sector_returns==0).sum())
    if total==0 or pos+neg+unchanged!=total: return {**empty,"mapped":mapped,"priced":priced,"coverage":f"{priced}/500"}
    return {"available":True,"alignment_pct":((pos-neg)/total*100),"mapped":mapped,"priced":priced,"sectors":total,"positive_sectors":pos,"negative_sectors":neg,"unchanged_sectors":unchanged,"coverage":f"{priced}/500"}
