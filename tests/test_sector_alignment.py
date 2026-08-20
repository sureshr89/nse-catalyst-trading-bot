import pandas as pd
import pytest
from data.sector_alignment import build_sector_map, calculate_sector_alignment


def test_sector_map_rejects_incomplete_universe():
    u=pd.DataFrame({"Symbol":["A","B"],"Sector":["IT","Bank"]})
    with pytest.raises(ValueError, match="incomplete"):
        build_sector_map(u)


def test_sector_alignment_requires_all_500_priced():
    sm=pd.DataFrame({"Symbol":["A","B"],"Sector":["IT","Bank"]})
    prices=pd.DataFrame({"Symbol":["A"],"change_pct":[1.0]})
    result=calculate_sector_alignment(prices,sm)
    assert result["available"] is False
    assert result["priced"] == 1


def test_sector_alignment_is_equal_weighted_by_sector():
    sm=pd.DataFrame({"Symbol":[f"S{i}" for i in range(500)],"Sector":["A"]*250+["B"]*250})
    prices=pd.DataFrame({"Symbol":sm["Symbol"],"change_pct":[1.0]*250+[-1.0]*250})
    result=calculate_sector_alignment(prices,sm)
    assert result["available"] is True
    assert result["sectors"] == 2
    assert result["positive_sectors"] == 1
    assert result["negative_sectors"] == 1
    assert result["alignment_pct"] == 0.0
