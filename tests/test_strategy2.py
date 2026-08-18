from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from strategy import gap_extension_reversal_engine as module
from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine

IST = ZoneInfo("Asia/Kolkata")


def _data(closes, highs=None, lows=None, start="09:45"):
    base = datetime.now(IST).replace(hour=int(start[:2]), minute=int(start[3:]), second=0, microsecond=0)
    highs = highs or closes
    lows = lows or [min(c, h) for c, h in zip(closes, highs)]
    rows = []
    for i, (close, high, low) in enumerate(zip(closes, highs, lows)):
        stamp = base + pd.Timedelta(minutes=i)
        rows.append({"Datetime": stamp, "Open": close, "High": high, "Low": low, "Close": close})
    return pd.DataFrame(rows), base + pd.Timedelta(minutes=len(closes))


class _FakeLive:
    def __init__(self, price): self.price = float(price)
    def get_latest_live_price(self, symbol, max_age_seconds=2):
        return {"Close": self.price, "High": self.price, "Low": self.price}


def test_strategy2_requires_open_above_pdh_for_sell(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(102.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([104, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, -0.1, 99, as_of=as_of) is None


def test_strategy2_sell_uses_live_ltp_after_extension(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(107.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([111, 109, 108], [111, 110, 109])
    result = engine.evaluate("TEST", data, 110, 100, 100, -0.2, 99, as_of=as_of)
    assert result is not None
    assert result["signal"] == "SELL"
    assert result["entry"] == 107.0
    assert result["target"] == 100.0
    assert result["stop_loss"] == 111.0
    assert result["entry_source"] == "LIVE_LTP"


def test_strategy2_does_not_use_first_completed_close_as_entry(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(106.5))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([111, 107, 102], [111, 108, 107])
    result = engine.evaluate("TEST", data, 110, 100, 100, -0.2, 99, as_of=as_of)
    assert result is not None
    assert result["entry"] == 106.5
    assert result["entry"] != 107.0


def test_strategy2_uses_trigger_day_high_including_pre_0945_extension(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(109.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    base = datetime.now(IST).replace(hour=9, minute=30, second=0, microsecond=0)
    data = pd.DataFrame([
        {"Datetime": base, "Open": 110, "High": 115, "Low": 109, "Close": 112},
        {"Datetime": base + pd.Timedelta(minutes=15), "Open": 110, "High": 111, "Low": 109, "Close": 111},
        {"Datetime": base + pd.Timedelta(minutes=16), "Open": 111, "High": 110, "Low": 108, "Close": 109},
    ])
    result = engine.evaluate("TEST", data, 110, 100, 100, -0.2, 99, as_of=base + pd.Timedelta(minutes=17))
    assert result is not None
    assert result["entry"] == 109.0
    assert result["stop_loss"] == 115.0


def test_strategy2_small_positive_nifty_is_allowed_for_sell(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(102.5))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, 0.1, 99, as_of=as_of) is not None


def test_strategy2_rejects_clearly_bullish_nifty_for_sell(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(102.5))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, 0.3, 99, as_of=as_of) is None


def test_strategy2_buy_mirror_rule(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(93.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([90.5, 91.0, 92.0], highs=[91.0, 91.2, 92.5], lows=[89.9, 89.9, 90.0])
    result = engine.evaluate("TEST", data, 90, 102, 100, 0.1, 100, as_of=as_of)
    assert result is not None
    assert result["signal"] == "BUY"
    assert result["entry"] == 93.0
    assert result["target"] == 100.0
    assert result["stop_loss"] == 89.9


def test_strategy2_buy_requires_open_below_pdl(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(93.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([90.5, 91.0, 93.0], lows=[89.9, 89.9, 92.8])
    assert engine.evaluate("TEST", data, 103, 102, 100, 0.1, 100, as_of=as_of) is None


def test_strategy2_buy_rejects_clearly_bearish_nifty(monkeypatch):
    monkeypatch.setattr(module, "_LIVE", _FakeLive(93.0))
    engine = GapExtensionReversalEngine("00:00", "23:59", 1.25)
    data, as_of = _data([90.5, 91.0, 93.0], highs=[91.0, 91.2, 93.2], lows=[89.9, 89.9, 92.8])
    assert engine.evaluate("TEST", data, 90, 102, 100, -0.3, 100, as_of=as_of) is None


def test_strategy2_has_no_atr_dependency():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    assert not hasattr(engine, "atr")
