import pandas as pd


def test_cycle_configuration_is_15_plus_10():
    from config.settings import COLLECTION_WINDOW_SECONDS, DECISION_WINDOW_SECONDS, SCAN_INTERVAL_SECONDS
    assert COLLECTION_WINDOW_SECONDS == 15
    assert DECISION_WINDOW_SECONDS == 10
    assert SCAN_INTERVAL_SECONDS == 25


def test_news_ranker_filters_by_side(monkeypatch):
    import market.news_ranker as nr
    with nr._LOCK:
        nr._CACHE.clear()
        now = nr._now()
        nr._CACHE.update({
            "AAA": {"score": 80.0, "headlines": [], "updated_at": now},
            "BBB": {"score": -70.0, "headlines": [], "updated_at": now},
            "CCC": {"score": 10.0, "headlines": [], "updated_at": now},
        })
    assert nr.rank(["AAA", "BBB", "CCC"], "BUY") == [("AAA", 80.0), ("CCC", 10.0)]
    assert nr.rank(["AAA", "BBB", "CCC"], "SELL") == [("BBB", -70.0)]
