"""NIFTY 500 sector mapping and integrity-checked sector alignment."""
from pathlib import Path
import pandas as pd
from config.settings import MAX_STOCKS, MIN_DATA_COVERAGE_COUNT

CACHE = Path("data/nifty500_sector_map.csv")
REQUIRED = MAX_STOCKS


def _norm(x):
    return str(x).upper().strip().replace(".NS", "")


def _normalise_sector(value):
    text = str(value).strip()
    if text.upper() in {"", "UNKNOWN", "NAN", "NONE", "<NA>", "NULL"}:
        return pd.NA
    return text


def build_sector_map(universe):
    if universe is None or universe.empty or "Symbol" not in universe.columns:
        raise ValueError("NIFTY 500 universe unavailable")

    # Sector alignment must use a genuine sector classification. Industry is
    # a different level and must never silently become the sector field.
    sector_col = next(
        (
            c
            for c in [
                "Sector",
                "Sector Name",
                "Macro Economic Sector",
                "Macro-Economic Sector",
            ]
            if c in universe.columns
        ),
        None,
    )
    if sector_col is None:
        raise ValueError("NIFTY 500 sector column unavailable")

    out = universe[["Symbol", sector_col]].rename(columns={sector_col: "Sector"}).copy()
    out["Symbol"] = out["Symbol"].map(_norm)
    out["Sector"] = out["Sector"].map(_normalise_sector)
    out = (
        out.dropna(subset=["Symbol", "Sector"])
        .drop_duplicates("Symbol")
        .reset_index(drop=True)
    )
    if len(out) != REQUIRED:
        raise ValueError(f"Sector mapping incomplete: {len(out)}/{REQUIRED}")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CACHE, index=False)
    return out


def load_sector_map(universe, refresh=False):
    expected = (
        set(_norm(s) for s in universe["Symbol"].dropna())
        if universe is not None and not universe.empty and "Symbol" in universe.columns
        else set()
    )
    if len(expected) != REQUIRED:
        raise ValueError(f"NIFTY 500 universe incomplete: {len(expected)}/{REQUIRED}")

    if not refresh and CACHE.exists():
        try:
            cached = pd.read_csv(CACHE)
            if {"Symbol", "Sector"}.issubset(cached.columns):
                cached["Symbol"] = cached["Symbol"].map(_norm)
                cached["Sector"] = cached["Sector"].map(_normalise_sector)
                cached = cached.dropna(subset=["Symbol", "Sector"]).drop_duplicates("Symbol")
                actual = set(cached["Symbol"])
                if len(cached) == REQUIRED and actual == expected:
                    return cached.reset_index(drop=True)
        except Exception:
            pass
    return build_sector_map(universe)


def calculate_sector_alignment(prices, sector_map, price_col="change_pct"):
    empty = {
        "available": False,
        "alignment_pct": None,
        "mapped": 0,
        "priced": 0,
        "sectors": 0,
        "positive_sectors": 0,
        "negative_sectors": 0,
        "unchanged_sectors": 0,
        "coverage": f"0/{REQUIRED}",
    }
    if prices is None or prices.empty or sector_map is None or sector_map.empty:
        return empty
    if (
        not {"Symbol", "Sector"}.issubset(sector_map.columns)
        or "Symbol" not in prices.columns
        or price_col not in prices.columns
    ):
        return empty

    p = prices[["Symbol", price_col]].copy()
    p["Symbol"] = p["Symbol"].map(_norm)
    p[price_col] = pd.to_numeric(p[price_col], errors="coerce")
    p = p.dropna(subset=["Symbol", price_col]).drop_duplicates("Symbol", keep="last")

    m = sector_map[["Symbol", "Sector"]].copy()
    m["Symbol"] = m["Symbol"].map(_norm)
    m["Sector"] = m["Sector"].map(_normalise_sector)
    m = m.dropna(subset=["Symbol", "Sector"]).drop_duplicates("Symbol")

    merged = m.merge(p, on="Symbol", how="left")
    mapped = int(m["Symbol"].nunique())
    priced = int(merged[price_col].notna().sum())

    # The strategy contract requires at least 490 priced constituents before
    # sector majority can influence a trade. Missing prices therefore do not
    # get treated as neutral sectors and cannot manufacture an alignment.
    if priced < MIN_DATA_COVERAGE_COUNT:
        return {
            **empty,
            "mapped": mapped,
            "priced": priced,
            "coverage": f"{priced}/{REQUIRED}",
        }

    sector_returns = merged.dropna(subset=[price_col]).groupby("Sector", sort=True)[price_col].mean()
    total = int(len(sector_returns))
    pos = int((sector_returns > 0).sum())
    neg = int((sector_returns < 0).sum())
    unchanged = int((sector_returns == 0).sum())
    if total == 0 or pos + neg + unchanged != total:
        return {
            **empty,
            "mapped": mapped,
            "priced": priced,
            "coverage": f"{priced}/{REQUIRED}",
        }

    return {
        "available": True,
        "alignment_pct": (pos - neg) / total * 100,
        "mapped": mapped,
        "priced": priced,
        "sectors": total,
        "positive_sectors": pos,
        "negative_sectors": neg,
        "unchanged_sectors": unchanged,
        "coverage": f"{priced}/{REQUIRED}",
    }
