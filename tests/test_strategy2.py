from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine

IST = ZoneInfo("Asia/Kolkata")


def _data(closes, highs=None):
    now = datetime.now(IST).replace(second=0, microsecond=0)
    highs = highs or closes
    rows = []
    for i, (close, high) in enumerate(zip(closes, highs), 1):
        stamp = now - pd.Timedelta(minutes=len(closes) - i + 1)
        rows.append({"Datetime": stamp, "Open": close, "High": high, "Low": min(close, high), "Close": close})
    return pd.DataFrame(rows)


def test_strategy2_requires_open_above_pdh_and_post_945_extension():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 103.5], [104, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, -0.1) is None


def test_strategy2_enters_on_first_completed_close_below_open():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    result = engine.evaluate("TEST", data, 103, 100, 100, -0.2)
    assert result is not None
    assert result["signal"] == "SELL"
    assert result["entry"] == 102.5
    assert result["target"] == 100.0
    assert result["stop_loss"] == 104.5


def test_strategy2_rejects_clearly_bullish_nifty():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    data = _data([104, 104.5, 102.5], [104.2, 104.5, 103.5])
    assert engine.evaluate("TEST", data, 103, 100, 100, 0.1) is None


def test_strategy2_has_no_atr_dependency():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    assert not hasattr(engine, "atr")
