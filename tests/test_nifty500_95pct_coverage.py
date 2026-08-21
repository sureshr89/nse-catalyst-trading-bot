import pandas as pd

import engine.master_engine as me
from config.settings import MIN_DATA_COVERAGE_COUNT, MAX_STOCKS
from data.sector_alignment import calculate_sector_alignment


def test_nifty500_98_percent_threshold_is_490():
    assert MAX_STOCKS == 500
    assert MIN_DATA_COVERAGE_COUNT == 490


def test_sector_alignment_accepts_490_of_500_verified_prices():
    symbols = [f"S{i}" for i in range(500)]
    sector_map = pd.DataFrame({"Symbol": symbols, "Sector": ["A"] * 250 + ["B"] * 250})
    prices = pd.DataFrame({"Symbol": symbols[:490], "change_pct": [1.0] * 250 + [-1.0] * 240})

    result = calculate_sector_alignment(prices, sector_map)

    assert result["available"] is True
    assert result["priced"] == 490
    assert result["coverage"] == "490/500"


def test_master_market_snapshot_accepts_490_verified_quotes(monkeypatch):
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
        "Symbol": symbols[:490], "SecurityId": [str(i) for i in range(490)]
    }))
    quotes = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(490)],
        "LTP": [101.0] * 250 + [99.0] * 240,
        "PreviousClose": [100.0] * 490,
        "change_pct": [1.0] * 250 + [-1.0] * 240,
        "TodayOpen": [100.0] * 490,
        "TodayHigh": [102.0] * 490,
        "TodayLow": [98.0] * 490,
    })
    monkeypatch.setattr(me, "market_quote", lambda mapping, cache_seconds=5: quotes)
    monkeypatch.setattr(me, "index_quote", lambda symbol: {
        "LTP": 101.0, "PreviousClose": 100.0, "NetChange": 1.0
    })
    monkeypatch.setattr(engine, "_write_diagnostics", lambda: None)

    snapshot = engine._market_snapshot()

    assert snapshot["verified"] is True
    assert len(snapshot["prices"]) == 490
    assert snapshot["ad_complete"] is True
    assert snapshot["sector"]["priced"] == 490
