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
    engine = RiskEngine()
    result = engine.validate({"symbol": "TEST", "signal": "BUY", "entry": 100.0, "stop_loss": 98.0, "target": 102.5}, check_trade_count=False)
    assert result["approved"] is True
    assert result["actual_risk"] == MAX_RISK_PER_TRADE
    assert result["rr"] >= MIN_RR_RATIO
    assert result["actual_risk"] >= MIN_REQUIRED_RISK


def test_risk_engine_rejects_wrong_side_stop():
    engine = RiskEngine()
    result = engine.validate({"symbol": "TEST", "signal": "SELL", "entry": 100.0, "stop_loss": 99.0, "target": 98.0}, check_trade_count=False)
    assert result["approved"] is False
    assert any("SELL stop loss" in reason for reason in result["reasons"])


def test_buy_state_requires_breach_then_return_to_open():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    state = {"side": "BUY", "pdh_breached": False, "open_returned": False}
    state = engine.update_state(state, 105.0, 100.0, 95.0, 99.5)
    assert state["pdh_breached"] is True
    assert state.get("open_returned", False) is False
    state = engine.update_state(state, 105.0, 100.0, 95.0, 105.0)
    assert state["open_returned"] is True


def test_sell_state_requires_breach_then_return_to_open():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    state = {"side": "SELL", "pdl_breached": False, "open_returned": False}
    state = engine.update_state(state, 100.0, 100.0, 90.0, 90.5)
    assert state["pdl_breached"] is True
    assert state.get("open_returned", False) is False
    state = engine.update_state(state, 100.0, 100.0, 90.0, 100.0)
    assert state["open_returned"] is True


def test_build_signal_buy_target_and_stop():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    signal = engine.build_signal("TEST", "BUY", 105.0, 105.0, 100.0, 95.0, 0.5)
    assert signal["stop_loss"] == 100.0
    assert signal["target"] == 111.25
    assert signal["risk_reward"] == 1.25


def test_build_signal_sell_target_and_stop():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    signal = engine.build_signal("TEST", "SELL", 85.0, 85.0, 105.0, 90.0, -0.5)
    assert signal["stop_loss"] == 90.0
    assert signal["target"] == 78.75
    assert signal["risk_reward"] == 1.25


def test_candidate_metadata_contains_no_secondary_priority_metric():
    result = metrics()
    assert result == {"metrics_calculated_at": result["metrics_calculated_at"]}


def test_highest_gap_is_always_first():
    high_gap = {"gap_percent": 4.0}
    lower_gap = {"gap_percent": 2.0}
    assert sort_key(high_gap) > sort_key(lower_gap)


def test_gap_priority_uses_magnitude_for_sell():
    larger_sell_gap = {"gap_percent": -5.0}
    smaller_sell_gap = {"gap_percent": -2.0}
    assert sort_key(larger_sell_gap) > sort_key(smaller_sell_gap)


def test_equal_gap_has_equal_priority():
    assert sort_key({"gap_percent": 3.0}) == sort_key({"gap_percent": -3.0})


def test_paper_pnl_buy_and_sell():
    assert PaperTradeEngine.calculate_pnl("BUY", 100, 102.5, 10) == 25.0
    assert PaperTradeEngine.calculate_pnl("SELL", 100, 97.5, 10) == 25.0


def test_strategy_uses_completed_minute_close_not_forming_candle():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    now = datetime.now(IST).replace(second=0, microsecond=0)
    previous = now - pd.Timedelta(minutes=2)
    last_completed = now - pd.Timedelta(minutes=1)
    data = pd.DataFrame([
        {"Datetime": previous, "Open": 105, "High": 106, "Low": 99, "Close": 99.5},
        {"Datetime": last_completed, "Open": 99.5, "High": 106, "Low": 99, "Close": 105},
        {"Datetime": now, "Open": 105, "High": 110, "Low": 104, "Close": 110},
    ])
    completed = engine.latest_completed(data)
    assert completed is not None
    assert completed["Close"] == 105


def test_build_ignores_forming_candle_for_setup_state():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    now = datetime.now(IST).replace(second=0, microsecond=0)
    previous = now - pd.Timedelta(minutes=1)
    data = pd.DataFrame([
        {"Datetime": previous, "Open": 105, "High": 106, "Low": 99, "Close": 99.5},
        {"Datetime": now, "Open": 99.5, "High": 106, "Low": 99, "Close": 105},
    ])
    signal = engine.build("TEST", data, 100.0, 95.0, today_open=105.0, nifty_change_pct=0.5)
    assert signal is None


def test_user_facing_dashboard_has_no_legacy_volatility_labels():
    files = [
        ROOT / "dashboard" / "app.py",
        ROOT / "dashboard" / "pages" / "current_trading.py",
        ROOT / "dashboard" / "pages" / "analysis.py",
        ROOT / "dashboard" / "pages" / "news_analysis.py",
        ROOT / "dashboard" / "pages" / "downloads.py",
        ROOT / "dashboard" / "pages" / "stock_scanner.py",
    ]
    forbidden = ["atr analysis", "atr%", "atr_pct", "average true range"]
    for path in files:
        source = path.read_text(encoding="utf-8").lower()
        for label in forbidden:
            assert label not in source, f"Legacy volatility label '{label}' remains in {path}"
