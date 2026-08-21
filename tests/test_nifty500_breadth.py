import pandas as pd
import market.nifty500_breadth as nb


def test_incomplete_universe_is_rejected(monkeypatch):
    b = nb.Nifty500Breadth()
    monkeypatch.setattr(b, "_get_universe", lambda: pd.DataFrame({"Symbol": ["A", "B"], "Sector": ["X", "Y"]}))
    result = b.snapshot(force=True)
    assert result["complete"] is False
    assert result["evaluated"] == 2
    assert "UNKNOWN" in result["direction"]


def test_allows_requires_complete_breadth(monkeypatch):
    b = nb.Nifty500Breadth()
    bullish = {"complete": True, "sector_complete": True, "nifty500_change_pct": 0.5, "sector_alignment_pct": 1.0, "ad_ratio": 1.5}
    monkeypatch.setattr(b, "snapshot", lambda force=False: bullish)
    allowed, snapshot = b.allows("BUY")
    assert allowed is True
    assert snapshot is bullish
    bearish = {**bullish, "nifty500_change_pct": -0.5, "sector_alignment_pct": -1.0, "ad_ratio": 0.5}
    monkeypatch.setattr(b, "snapshot", lambda force=False: bearish)
    allowed, snapshot = b.allows("SELL")
    assert allowed is True
    assert snapshot is bearish


def test_allows_rejects_incomplete_snapshot(monkeypatch):
    b = nb.Nifty500Breadth()
    monkeypatch.setattr(b, "snapshot", lambda force=False: {"complete": False, "sector_complete": False})
    assert b.allows("BUY")[0] is False
