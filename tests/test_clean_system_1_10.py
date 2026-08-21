from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_01_strategy_contract_has_exactly_s1_to_s5():
    from strategy.nifty500_price_action_strategies import STRATEGY_DEFINITIONS
    from strategy.contracts import STRATEGY_RULES
    assert set(STRATEGY_DEFINITIONS) == {"S1", "S2", "S3", "S4", "S5"}
    assert set(STRATEGY_RULES) == {"S1", "S2", "S3", "S4", "S5"}


def test_02_master_engine_is_single_runtime_entry():
    from engine.master_engine import MasterEngine
    from main import TradingBot
    assert TradingBot is MasterEngine
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "MasterEngine" in source
    assert "open_reversal_engine" not in source
    assert "gap_extension_reversal_engine" not in source


def test_03_legacy_patch_layers_are_absent():
    legacy = [
        "engine/authoritative_dhan_snapshot_patch.py", "engine/diagnostic_consistency_patch.py",
        "engine/live_data_alignment_patch.py", "engine/stability_patch.py",
        "engine/strategy_diagnostics_patch.py", "engine/trade_path_fix.py",
        "engine/strategy_sector_count_gate_patch.py", "engine/execution_diagnostics_patch.py",
        "engine/dhan_patch.py",
    ]
    assert all(not (ROOT / p).exists() for p in legacy)


def test_04_dhan_is_the_only_price_adapter():
    source = (ROOT / "market" / "price_data.py").read_text(encoding="utf-8").lower()
    dhan = (ROOT / "market" / "dhan_data.py").read_text(encoding="utf-8").lower()
    assert "yfinance" not in source and "yfinance" not in dhan
    assert "dhan" in source and "dhan" in dhan


def test_05_strategy_rules_have_common_market_gate():
    from strategy.nifty500_price_action_strategies import market_gate
    assert market_gate("BUY", 0.1, 1.0, 1.1, 500, 8, 4)
    assert market_gate("SELL", -0.1, -1.0, 0.9, 500, 4, 8)
    assert not market_gate("BUY", 0.1, 1.0, 1.1, 489, 8, 4)
    assert not market_gate("BUY", -0.1, 1.0, 1.1, 500, 8, 4)
    assert not market_gate("SELL", 0.1, -1.0, 0.9, 500, 4, 8)
    assert not market_gate("BUY", 0.1, 1.0, 1.1, 500, 4, 8)


def test_06_all_five_strategies_produce_correct_side_and_rr():
    from strategy.nifty500_price_action_strategies import evaluate_s1, evaluate_s2, evaluate_s3, evaluate_s4, evaluate_s5
    g = dict(nifty500_change_pct=0.2, sector_alignment_pct=1.0, ad_ratio=1.2, ad_coverage=500,
             positive_sectors=8, negative_sectors=4, previous_candle_open=100, previous_candle_close=101)
    assert evaluate_s1("T", "BUY", 110, 100, 90, 99, 115, 111, **g)
    assert evaluate_s2("T", "BUY", 100, 90, 99, 120, 101, True, **g)
    assert evaluate_s3("T", "BUY", 110, 120, 100, 98, 115, 111, **g)
    assert evaluate_s4("T", "BUY", 120, 98, 115, 105, 116, **g)
    assert evaluate_s5("T", "BUY", 100, 90, 101, **g)
    for fn, args in [
        (evaluate_s1, ("T", "BUY", 110, 100, 90, 99, 115, 111)),
        (evaluate_s2, ("T", "BUY", 100, 90, 99, 120, 101, True)),
        (evaluate_s3, ("T", "BUY", 110, 120, 100, 98, 115, 111)),
        (evaluate_s4, ("T", "BUY", 120, 98, 115, 105, 116)),
        (evaluate_s5, ("T", "BUY", 100, 90, 101)),
    ]:
        sig = fn(*args, **g)
        assert sig is not None and sig.side == "BUY" and sig.rr == 1.25
        assert sig.stop_loss < sig.entry < sig.target


def test_07_risk_limits_match_configuration():
    from config.settings import ALLOCATED_CAPITAL_PER_TRADE, MIN_REQUIRED_RISK, MAX_RISK_PER_TRADE, MIN_RR_RATIO, MAX_TRADES_PER_STRATEGY_PER_DAY, DAILY_MAX_LOSS_PER_STRATEGY
    assert ALLOCATED_CAPITAL_PER_TRADE == 250000
    assert MIN_REQUIRED_RISK == 1400
    assert MAX_RISK_PER_TRADE == 1500
    assert MIN_RR_RATIO == 1.25
    assert MAX_TRADES_PER_STRATEGY_PER_DAY == 1
    assert DAILY_MAX_LOSS_PER_STRATEGY == 1500


def test_08_no_yahoo_dependency_or_active_legacy_strategy_imports():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "yfinance" not in req
    for folder in ["engine", "market", "strategy", "main.py"]:
        path = ROOT / folder
        files = [path] if path.is_file() else list(path.rglob("*.py"))
        for file in files:
            text = file.read_text(encoding="utf-8").lower()
            assert "from strategy.open_reversal_engine" not in text
            assert "from strategy.gap_extension_reversal_engine" not in text


def test_09_paper_trading_only():
    from config.settings import PAPER_TRADING, LIVE_TRADING, SQUARE_OFF_TIME, TRADING_START, LAST_ENTRY_TIME
    assert PAPER_TRADING is True and LIVE_TRADING is False
    assert TRADING_START == "09:45" and LAST_ENTRY_TIME == "14:00" and SQUARE_OFF_TIME == "15:00"


def test_10_contract_and_diagnostics_are_consistent():
    from strategy.contracts import STRATEGY_VERSION, strategy_metadata
    from engine.master_engine import MasterEngine
    assert STRATEGY_VERSION == "2026.08.21.clean-dhan-v2"
    for s in ("S1", "S2", "S3", "S4", "S5"):
        assert strategy_metadata(s)["strategy"] == s
        assert strategy_metadata(s)["version"] == STRATEGY_VERSION
    diag = MasterEngine._blank_diag(MasterEngine.__new__(MasterEngine))
    assert diag["strategy_version"] == "clean-dhan-v3"
    assert diag["market_data_source"] == "DHAN_ONLY"
    assert set(diag["signals_by_strategy"]) == {"S1", "S2", "S3", "S4", "S5"}
