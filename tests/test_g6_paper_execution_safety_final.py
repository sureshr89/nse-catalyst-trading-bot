"""G6 regression checks for paper-only execution and trade lifecycle safety."""
from datetime import datetime, timezone
from unittest.mock import patch

from papertrade.paper_trade_engine import PaperTradeEngine


def _engine(tmp_path):
    with patch.object(PaperTradeEngine, "_state_path", return_value=str(tmp_path / "paper_state.json")):
        e = PaperTradeEngine()
    e.open_positions = {}
    e.closed_positions = []
    e.trade_counter = 0
    e.total_capital = 100_000.0
    e.available_capital = 100_000.0
    e.used_capital = 0.0
    return e


def _valid_trade():
    return {
        "approved": True,
        "symbol": "ABC",
        "signal": "BUY",
        "setup_type": "S1",
        "entry": 100.0,
        "stop_loss": 98.6,
        "target": 101.75,
        "quantity": 1000,
        "actual_risk": 1400.0,
        "entry_time": datetime(2026, 8, 21, 10, 0, 0),
    }


def test_live_trading_flag_can_never_open_paper_trade(tmp_path):
    e = _engine(tmp_path)
    e.live_trading = True
    result = e.open_trade(_valid_trade())
    assert result["opened"] is False
    assert not e.open_positions


def test_unapproved_trade_cannot_open(tmp_path):
    e = _engine(tmp_path)
    trade = _valid_trade()
    trade["approved"] = False
    result = e.open_trade(trade)
    assert result["opened"] is False
    assert not e.open_positions


def test_duplicate_symbol_cannot_open_twice(tmp_path):
    e = _engine(tmp_path)
    first = e.open_trade(_valid_trade())
    assert first["opened"] is True
    second = e.open_trade(_valid_trade())
    assert second["opened"] is False
    assert len(e.open_positions) == 1


def test_stop_closes_buy_position_and_releases_capital(tmp_path):
    e = _engine(tmp_path)
    opened = e.open_trade(_valid_trade())
    assert opened["opened"] is True
    closed = e.close_position("ABC", 98.6, datetime(2026, 8, 21, 10, 31), "STOP_LOSS")
    assert closed is not None
    assert closed["status"] == "CLOSED"
    assert closed["pnl"] == -1400.0
    assert not e.open_positions
    assert e.available_capital == e.total_capital


def test_ambiguous_bar_uses_stop_first(tmp_path):
    e = _engine(tmp_path)
    assert e.open_trade(_valid_trade())["opened"] is True

    import papertrade.paper_trade_engine as engine_module
    real_datetime = datetime

    class FixedSessionDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            utc_value = real_datetime(2026, 8, 21, 5, 0, 0, tzinfo=timezone.utc)
            return utc_value.astimezone(tz) if tz is not None else utc_value.replace(tzinfo=None)

    with patch.object(engine_module, "datetime", FixedSessionDateTime):
        result = e.process_live_price("ABC", 101.0, high=102.0, low=98.0)

    assert result is not None
    assert result["exit_reason"] == "AMBIGUOUS_LIVE_BAR_STOP_FIRST"
    assert result["exit_price"] == 98.6
