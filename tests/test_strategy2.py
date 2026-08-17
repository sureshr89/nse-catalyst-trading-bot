from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd

from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine

IST = ZoneInfo("Asia/Kolkata")


def _data(closes, highs=None, lows=None):
    # Strategy 2 correctly stops accepting NEW entries at 14:00 IST.
    # Keep synthetic trigger candles before that cutoff so tests are independent
    # of the CI runner's wall-clock time.
    base = datetime.now(IST).replace(hour=13, minute=55, second=0, microsecond=0)
    highs = highs or closes
    lows = lows or [min(c, h) for c, h in zip(closes, highs)]
    rows = []
    for i, (close, high, low) in enumerate(zip(closes, highs, lows), 1):
        stamp = base + pd.Timedelta(minutes=i - 1)
        rows.append({"Datetime": stamp, "Open": close, "High": high, "Low": low, "Close": close})
    return pd.DataFrame(rows)


def test_strategy2_requires_open_above_pdh_for_sell():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, -0.1, 99) is None


def test_strategy2_enters_on_first_completed_close_below_open_sell():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    result = engine.evaluate("TEST", data, 103, 100, 100, -0.2, 99)
    assert result is not None
    assert result["signal"] == "SELL"
    assert result["entry"] == 102.5
    assert result["target"] == 100.0
    assert result["stop_loss"] == 104.5


def test_strategy2_first_sell_close_is_only_trigger():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104.5, 100.9, 100.5], [104.5, 103.2, 102.0])
    assert engine.evaluate("TEST", data, 103, 100, 100, -0.2, 99) is None


def test_strategy2_small_positive_nifty_is_allowed_for_sell():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, 0.1, 99) is not None


def test_strategy2_rejects_clearly_bullish_nifty_for_sell():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, 0.3, 99) is None


def test_strategy2_buy_mirror_rule():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([90.5, 91.0, 93.0], highs=[91.0, 91.2, 93.2], lows=[89.9, 89.9, 92.8])
    result = engine.evaluate("TEST", data, 90, 102, 100, 0.1, 100)
    assert result is not None
    assert result["signal"] == "BUY"
    assert result["entry"] == 93.0
    assert result["target"] == 100.0
    assert result["stop_loss"] == 89.9


def test_strategy2_buy_requires_open_below_pdl():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([90.5, 91.0, 93.0], lows=[89.9, 89.9, 92.8])
    assert engine.evaluate("TEST", data, 103, 102, 100, 0.1, 100) is None


def test_strategy2_buy_rejects_clearly_bearish_nifty():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([90.5, 91.0, 93.0], highs=[91.0, 91.2, 93.2], lows=[89.9, 89.9, 92.8])
    assert engine.evaluate("TEST", data, 90, 102, 100, -0.3, 100) is None


def test_strategy2_has_no_atr_dependency():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    assert not hasattr(engine, "atr")
