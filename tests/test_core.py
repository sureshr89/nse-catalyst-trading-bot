from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import MAX_RISK_PER_TRADE, MIN_REQUIRED_RISK, MIN_RR_RATIO
from papertrade.paper_trade_engine import PaperTradeEngine
from strategy.candidate_metrics import metrics, sort_key
from strategy.open_reversal_engine import OpenReversalEngine
from strategy.risk_engine import RiskEngine

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]


def test_risk_engine_approves_target_risk_trade():
    result = RiskEngine().validate({"symbol": "TEST", "signal": "BUY", "entry": 100.0, "stop_loss": 98.0, "target": 102.5}, check_trade_count=False)
    assert result["approved"] is True
    assert result["actual_risk"] == MAX_RISK_PER_TRADE
    assert result["rr"] >= MIN_RR_RATIO
    assert result["actual_risk"] >= MIN_REQUIRED_RISK


def test_risk_engine_rejects_wrong_side_stop():
    result = RiskEngine().validate({"symbol": "TEST", "signal": "SELL", "entry": 100.0, "stop_loss": 99.0, "target": 98.0}, check_trade_count=False)
    assert result["approved"] is False
    assert any("SELL stop loss" in reason for reason in result["reasons"])


def test_buy_state_requires_breach_then_return_to_open(monkeypatch):
    from strategy import open_reversal_engine as module
    class FakeLive:
        def __init__(self): self.price = 99.5
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {"Close": self.price}
    fake = FakeLive(); monkeypatch.setattr(module, "_LIVE", fake)
    engine = OpenReversalEngine("00:00", "23:59", 1.25)
    state = {"symbol": "TEST", "side": "BUY", "pdh_breached": False, "open_returned": False}
    state = engine.update_state(state, 105.0, 100.0, 95.0, 99.5)
    assert state["pdh_breached"] is False
    fake.price = 100.5; state = engine.update_state(state, 105.0, 100.0, 95.0, 105.0)
    assert state["pdh_breached"] is True
    assert state.get("open_returned", False) is False
    fake.price = 105.0; state = engine.update_state(state, 105.0, 100.0, 95.0, 105.0)
    assert state["open_returned"] is True


def test_sell_state_requires_breach_then_return_to_open(monkeypatch):
    from strategy import open_reversal_engine as module
    class FakeLive:
        def __init__(self): self.price = 101.0
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {"Close": self.price}
    fake = FakeLive(); monkeypatch.setattr(module, "_LIVE", fake)
    engine = OpenReversalEngine("00:00", "23:59", 1.25)
    state = {"symbol": "TEST", "side": "SELL", "pdl_breached": False, "open_returned": False}
    state = engine.update_state(state, 90.0, 105.0, 100.0, 101.0)
    assert state["pdl_breached"] is False
    fake.price = 99.0; state = engine.update_state(state, 90.0, 105.0, 100.0, 90.5)
    assert state["pdl_breached"] is True
    assert state.get("open_returned", False) is False
    fake.price = 89.0; state = engine.update_state(state, 90.0, 105.0, 100.0, 90.0)
    assert state["open_returned"] is True


def test_build_signal_buy_target_and_stop():
    signal = OpenReversalEngine("09:45", "14:00", 1.25).build_signal("TEST", "BUY", 105.0, 105.0, 100.0, 95.0, 0.5)
    assert signal["stop_loss"] == 100.0
    assert signal["target"] == 111.25
    assert signal["risk_reward"] == 1.25


def test_build_signal_sell_target_and_stop():
    signal = OpenReversalEngine("09:45", "14:00", 1.25).build_signal("TEST", "SELL", 85.0, 85.0, 105.0, 90.0, -0.5)
    assert signal["stop_loss"] == 90.0
    assert signal["target"] == 78.75
    assert signal["risk_reward"] == 1.25


def test_candidate_metadata_contains_no_secondary_priority_metric():
    result = metrics()
    assert result == {"metrics_calculated_at": result["metrics_calculated_at"]}


def test_highest_gap_is_always_first():
    assert sort_key({"gap_percent": 4.0}) > sort_key({"gap_percent": 2.0})


def test_gap_priority_uses_magnitude_for_sell():
    assert sort_key({"gap_percent": -5.0}) > sort_key({"gap_percent": -2.0})


def test_equal_gap_has_equal_priority():
    assert sort_key({"gap_percent": 3.0}) == sort_key({"gap_percent": -3.0})


def test_paper_pnl_buy_and_sell():
    assert PaperTradeEngine.calculate_pnl("BUY", 100, 102.5, 10) == 25.0
    assert PaperTradeEngine.calculate_pnl("SELL", 100, 97.5, 10) == 25.0


def test_strategy_uses_completed_minute_close_not_forming_candle():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    now = datetime.now(IST).replace(second=0, microsecond=0)
    data = pd.DataFrame([
        {"Datetime": now - pd.Timedelta(minutes=2), "Open": 105, "High": 106, "Low": 99, "Close": 99.5},
        {"Datetime": now - pd.Timedelta(minutes=1), "Open": 99.5, "High": 106, "Low": 99, "Close": 105},
        {"Datetime": now, "Open": 105, "High": 110, "Low": 104, "Close": 110},
    ])
    completed = engine.latest_completed(data)
    assert completed is not None
    assert completed["Close"] == 105


def test_build_ignores_forming_candle_for_setup_state(monkeypatch):
    from strategy import open_reversal_engine as module
    class FakeLive:
        def get_latest_live_price(self, symbol, max_age_seconds=2): return {"Close": 104.0}
    monkeypatch.setattr(module, "_LIVE", FakeLive())
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    now = datetime.now(IST).replace(second=0, microsecond=0)
    data = pd.DataFrame([
        {"Datetime": now - pd.Timedelta(minutes=1), "Open": 105, "High": 106, "Low": 99, "Close": 99.5},
        {"Datetime": now, "Open": 99.5, "High": 106, "Low": 99, "Close": 105},
    ])
    assert engine.build("TEST", data, 100.0, 95.0, today_open=105.0, nifty_change_pct=0.5) is None


def test_user_facing_dashboard_has_no_legacy_volatility_labels():
    files = [ROOT / "dashboard" / "app.py", ROOT / "dashboard" / "pages" / "current_trading.py", ROOT / "dashboard" / "pages" / "strategy2_current.py"]
    forbidden = ["atr analysis", "atr%", "atr_pct", "average true range"]
    for path in files:
        source = path.read_text(encoding="utf-8").lower()
        for label in forbidden:
            assert label not in source, f"Legacy volatility label '{label}' remains in {path}"


def test_dashboard_pages_are_exactly_the_two_active_strategy_pages():
    pages = sorted(p.name for p in (ROOT / "dashboard" / "pages").glob("*.py"))
    assert pages == ["current_trading.py", "strategy2_current.py"]
