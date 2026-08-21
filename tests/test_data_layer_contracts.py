import pandas as pd

from config.settings import MIN_DATA_COVERAGE_COUNT
from data.sector_alignment import build_sector_map, calculate_sector_alignment
from data.stock_universe import StockUniverse


def _universe(n=500):
    return pd.DataFrame(
        {
            "Symbol": [f"SYM{i}" for i in range(n)],
            "Industry": ["Industry A"] * n,
            "Sector": ["Sector A" if i % 2 == 0 else "Sector B" for i in range(n)],
        }
    )


def test_stock_universe_does_not_use_industry_as_sector():
    loader = StockUniverse()
    raw = pd.DataFrame({"Symbol": ["ABC"], "Industry": ["Banks"]})
    assert loader._clean(raw) is None


def test_stock_universe_requires_exact_500_and_real_sector():
    loader = StockUniverse()
    cleaned = loader._clean(_universe())
    assert cleaned is not None
    assert len(cleaned) == 500
    assert cleaned["Symbol"].nunique() == 500
    assert cleaned["Sector"].notna().all()


def test_sector_map_requires_exact_universe_match():
    universe = _universe()
    sector_map = build_sector_map(universe)
    assert len(sector_map) == 500
    assert set(sector_map["Symbol"]) == set(universe["Symbol"])

    prices = pd.DataFrame(
        {
            "Symbol": universe["Symbol"],
            "change_pct": [0.5] * MIN_DATA_COVERAGE_COUNT
            + [None] * (500 - MIN_DATA_COVERAGE_COUNT),
        }
    )
    result = calculate_sector_alignment(prices, sector_map)
    assert result["available"] is True
    assert result["priced"] >= MIN_DATA_COVERAGE_COUNT


def test_sector_alignment_rejects_insufficient_coverage():
    universe = _universe()
    sector_map = build_sector_map(universe)
    prices = pd.DataFrame(
        {
            "Symbol": universe["Symbol"].head(MIN_DATA_COVERAGE_COUNT - 1),
            "change_pct": [0.5] * (MIN_DATA_COVERAGE_COUNT - 1),
        }
    )
    result = calculate_sector_alignment(prices, sector_map)
    assert result["available"] is False
    assert result["priced"] == MIN_DATA_COVERAGE_COUNT - 1
