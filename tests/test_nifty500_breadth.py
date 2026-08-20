import pandas as pd
import market.nifty500_breadth as nb


def test_incomplete_universe_is_rejected(monkeypatch):
    b=nb.Nifty500Breadth()
    b._get_universe=lambda: pd.DataFrame({"Symbol":["A","B"],"Sector":["X","Y"]})
    result=b.snapshot(force=True)
    assert result["complete"] is False
    assert "NIFTY_500_UNIVERSE" in result["reason"]


def test_allows_requires_complete_breadth():
    b=nb.Nifty500Breadth()
    b._cached={"complete":True,"sector_complete":True,"nifty500_change_pct":0.5,"sector_alignment_pct":0.2,"ad_ratio":1.5}
    b._cached_at=0
    assert b.allows("BUY")[0] is True
    b._cached["nifty500_change_pct"]=-0.5
    b._cached["sector_alignment_pct"]=-0.2
    b._cached["ad_ratio"]=0.5
    assert b.allows("SELL")[0] is True


def test_allows_rejects_incomplete_snapshot():
    b=nb.Nifty500Breadth()
    b._cached={"complete":False,"sector_complete":False}
    b._cached_at=0
    assert b.allows("BUY")[0] is False
