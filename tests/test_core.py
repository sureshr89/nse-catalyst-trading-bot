from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import MAX_RISK_PER_TRADE, MIN_REQUIRED_RISK, MIN_RR_RATIO
from master_data import _prune_to_last_six_months
from papertrade.paper_trade_engine import PaperTradeEngine
from strategy.open_reversal_engine import OpenReversalEngine
from strategy.risk_engine import RiskEngine

IST = ZoneInfo("Asia/Kolkata")


def test_risk_engine_approves_target_risk_trade():
    engine = RiskEngine()
    result = engine.validate({
        "symbol": "TEST",
        "signal": "BUY",
        "entry": 100.0,
        "stop_loss": 98.0,
        "target": 102.5,
    }, check_trade_count=False)
    assert result["approved"] is True
    assert result["actual_risk"] == MAX_RISK_PER_TRADE
    assert result["rr"] >= MIN_RR_RATIO
    assert result["actual_risk"] >= MIN_REQUIRED_RISK


def test_risk_engine_rejects_wrong_side_stop():
    engine = RiskEngine()
    result = engine.validate({
        "symbol": "TEST",
        "signal": "SELL",
        "entry": 100.0,
        "stop_loss": 99.0,
        "target": 98.0,
    }, check_trade_count=False)
    assert result["approved"] is False
    assert any("SELL stop loss" in reason for reason in result["reasons"])


def test_strategy_target_and_trigger_stop_are_consistent():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    candle_time = datetime(2026, 8, 14, 10, 0, tzinfo=IST)
    trade = engine._trade(
        "SELL", "TEST", {
            "Datetime": candle_time,
            "Open": 105.0,
            "High": 106.0,
            "Low": 99.0,
            "Close": 100.0,
        },
        today_open=102.0,
        pdh=104.0,
        pdl=95.0,
        today_low=99.0,
        today_high=106.0,
        sector_direction="BEARISH",
        nifty_direction="BEARISH",
        stock_direction="BEARISH",
    )
    assert trade["stop_loss"] == 106.0
    assert trade["target"] == 92.5
    assert trade["risk_reward"] == 1.25


def test_paper_pnl_buy_and_sell():
    assert PaperTradeEngine.calculate_pnl("BUY", 100, 102.5, 10) == 25.0
    assert PaperTradeEngine.calculate_pnl("SELL", 100, 97.5, 10) == 25.0


def test_six_month_retention_keeps_current_and_previous_five(tmp_path):
    path = Path(tmp_path) / "master.csv"
    current = datetime.now(IST).date().replace(day=1)
    rows = []
    for offset in range(9):
        month = pd.Timestamp(current) - pd.DateOffset(months=offset)
        rows.append({"TradeDate": month.strftime("%Y-%m-10"), "Value": offset})
    pd.DataFrame(rows).to_csv(path, index=False)
    _prune_to_last_six_months(path, ["TradeDate"])
    result = pd.read_csv(path)
    assert len(result) == 6
    assert result["Value"].tolist() == [0, 1, 2, 3, 4, 5]
