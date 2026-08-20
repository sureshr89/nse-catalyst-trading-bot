import pandas as pd

import engine.master_engine as me
from config.settings import MIN_DATA_COVERAGE_COUNT, MAX_STOCKS
from data.sector_alignment import calculate_sector_alignment


def test_nifty500_95_percent_threshold_is_475():
    assert MAX_STOCKS == 500
    assert MIN_DATA_COVERAGE_COUNT == 475


def test_sector_alignment_accepts_475_of_500_verified_prices():
    symbols = [f"S{i}" for i in range(500)]
    sector_map = pd.DataFrame({"Symbol": symbols, "Sector": ["A"] * 250 + ["B"] * 250})
    prices = pd.DataFrame({"Symbol": symbols[:475], "change_pct": [1.0] * 250 + [-1.0] * 225})

    result = calculate_sector_alignment(prices, sector_map)

    assert result["available"] is True
    assert result["priced"] == 475
    assert result["coverage"] == "475/500"


def test_master_market_snapshot_accepts_475_verified_quotes(monkeypatch):
    engine = me.MasterEngine.__new__(me.MasterEngine)
    engine.references = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(500)],
        "PDH": [110.0] * 500,
        "PDL": [90.0] * 500,
        "PreviousDayClose": [100.0] * 500,
    })
    engine.sector_map = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(500)],
        "Sector": ["A"] * 250 + ["B"] * 250,
    })
    engine.diagnostics = {"rejections": {}}
    engine.last_snapshot = {}
    engine._session_date = None
    monkeypatch.setattr(engine, "_refresh_reference_data", lambda: None)
    monkeypatch.setattr(me, "configured", lambda: True)
    monkeypatch.setattr(me, "map_nifty500", lambda symbols: pd.DataFrame({
        "Symbol": symbols[:475], "SecurityId": [str(i) for i in range(475)]
    }))
    quotes = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(475)],
        "LTP": [101.0] * 250 + [99.0] * 225,
        "PreviousClose": [100.0] * 475,
        "change_pct": [1.0] * 250 + [-1.0] * 225,
        "TodayOpen": [100.0] * 475,
        "TodayHigh": [102.0] * 475,
        "TodayLow": [98.0] * 475,
    })
    monkeypatch.setattr(me, "market_quote", lambda mapping, cache_seconds=5: quotes)
    monkeypatch.setattr(me, "index_quote", lambda symbol: {
        "LTP": 101.0, "PreviousClose": 100.0, "NetChange": 1.0
    })
    monkeypatch.setattr(engine, "_write_diagnostics", lambda: None)

    snapshot = engine._market_snapshot()

    assert snapshot["verified"] is True
    assert len(snapshot["prices"]) == 475
    assert snapshot["ad_complete"] is True
    assert snapshot["sector"]["priced"] == 475
