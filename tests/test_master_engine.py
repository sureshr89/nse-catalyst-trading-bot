"""Focused tests for engine/master_engine.py without broker/network access."""
import pandas as pd
from engine.master_engine import MasterEngine


class FakePriceData:
    def today_only(self, df):
        return df.copy()


def _engine():
    engine = object.__new__(MasterEngine)
    engine.price_data = FakePriceData()
    engine.diagnostics = {"rejections": {}}
    engine.daily_counts = {"S1": 0, "S2": 0, "S3": 0, "S4": 0, "S5": 0}
    engine.daily_pnl_by_strategy = {"S1": 0.0, "S2": 0.0, "S3": 0.0, "S4": 0.0, "S5": 0.0}
    engine.last_signals = []
    return engine


def test_evaluate_stock_passes_only_strategy_contract_arguments():
    engine = _engine()
    ref = pd.Series({
        "Symbol": "ABC",
        "PDH": 100.0,
        "PDL": 90.0,
        "PreviousDayClose": 99.0,
    })
    snap = {
        "dhan_quotes": {
            "ABC": {
                "TodayOpen": 110.0,
                "TodayHigh": 115.0,
                "TodayLow": 98.0,
                "LTP": 111.0,
            }
        },
        "intraday": {
            "ABC": pd.DataFrame([
                {"Open": 108.0, "High": 109.0, "Low": 105.0, "Close": 108.0},
                {"Open": 109.0, "High": 110.0, "Low": 108.0, "Close": 109.0},
            ])
        },
        "nifty_change": 0.10,
        "sector": {"alignment_pct": 1.0, "positive_sectors": 10, "negative_sectors": 5},
        "ad_ratio": 1.2,
        "buy_alignment": True,
        "sell_alignment": False,
    }

    signals = engine._evaluate_stock("ABC", ref, snap)

    assert signals, "A valid S1 setup must reach the strategy engine"
    assert any(s["strategy"] == "S1" and s["symbol"] == "ABC" for s in signals)
    assert all(s["price_source"] == "Dhan" for s in signals)
    assert all(s["previous_day_close"] == 99.0 for s in signals)


def test_evaluate_stock_respects_market_alignment_before_strategy_calls():
    engine = _engine()
    ref = pd.Series({"Symbol": "ABC", "PDH": 100.0, "PDL": 90.0, "PreviousDayClose": 99.0})
    snap = {
        "dhan_quotes": {"ABC": {"TodayOpen": 110.0, "TodayHigh": 115.0, "TodayLow": 98.0, "LTP": 111.0}},
        "intraday": {"ABC": pd.DataFrame([{"Open": 108.0, "High": 109.0, "Low": 105.0, "Close": 108.0}])},
        "nifty_change": -0.10,
        "sector": {"alignment_pct": -1.0, "positive_sectors": 5, "negative_sectors": 10},
        "ad_ratio": 0.8,
        "buy_alignment": False,
        "sell_alignment": True,
    }
    signals = engine._evaluate_stock("ABC", ref, snap)
    assert signals == []
