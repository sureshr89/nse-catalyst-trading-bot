"""NIFTY 500 sector mapping and integrity-checked sector alignment."""
from pathlib import Path
import pandas as pd

CACHE=Path("data/nifty500_sector_map.csv")
REQUIRED=500

def build_sector_map(universe):
    if universe is None or universe.empty or "Symbol" not in universe.columns: raise ValueError("NIFTY 500 universe unavailable")
    sector_col=next((c for c in ["Sector","Industry"] if c in universe.columns),None)
    if sector_col is None: raise ValueError("NIFTY 500 sector/industry column unavailable")
    out=universe[["Symbol",sector_col]].rename(columns={sector_col:"Sector"}).copy()
    out["Symbol"]=out["Symbol"].astype(str).str.upper().str.strip();out["Sector"]=out["Sector"].astype(str).str.strip()
    out=out.replace({"Sector":{"":pd.NA,"UNKNOWN":pd.NA,"NAN":pd.NA}}).dropna(subset=["Symbol","Sector"]).drop_duplicates("Symbol")
    if len(out)<REQUIRED: raise ValueError(f"Sector mapping incomplete: {len(out)}/{REQUIRED}")
    CACHE.parent.mkdir(parents=True,exist_ok=True);out.to_csv(CACHE,index=False);return out

def load_sector_map(universe,refresh=False):
    if not refresh and CACHE.exists():
        try:
            cached=pd.read_csv(CACHE)
            if len(cached)>=REQUIRED and {"Symbol","Sector"}.issubset(cached.columns): return cached.drop_duplicates("Symbol")
        except Exception: pass
    return build_sector_map(universe)

def calculate_sector_alignment(prices,sector_map,price_col="change_pct"):
    empty={"available":False,"alignment_pct":None,"mapped":0,"priced":0,"sectors":0,"positive_sectors":0,"negative_sectors":0,"coverage":"0/500"}
    if prices is None or prices.empty or sector_map is None or sector_map.empty:return empty
    if not {"Symbol","Sector"}.issubset(sector_map.columns) or "Symbol" not in prices.columns or price_col not in prices.columns:return empty
    p=prices[["Symbol",price_col]].copy();p["Symbol"]=p["Symbol"].astype(str).str.upper().str.strip();p[price_col]=pd.to_numeric(p[price_col],errors="coerce")
    m=sector_map[["Symbol","Sector"]].copy();m["Symbol"]=m["Symbol"].astype(str).str.upper().str.strip()
    merged=m.merge(p,on="Symbol",how="left").dropna(subset=["Sector",price_col])
    if len(merged)<REQUIRED:return {**empty,"mapped":len(m),"priced":len(merged),"coverage":f"{len(merged)}/500"}
    sector_returns=merged.groupby("Sector")[price_col].mean();pos=int((sector_returns>0).sum());neg=int((sector_returns<0).sum());total=int(len(sector_returns));alignment=((pos-neg)/total*100) if total else None
    return {"available":alignment is not None,"alignment_pct":alignment,"mapped":len(m),"priced":len(merged),"sectors":total,"positive_sectors":pos,"negative_sectors":neg,"coverage":f"{len(merged)}/500"}
