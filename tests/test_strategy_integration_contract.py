from pathlib import Path

from strategy.contracts import STRATEGY_VERSION, strategy_metadata
from strategy.open_reversal_engine import OpenReversalEngine
from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine

ROOT = Path(__file__).resolve().parents[1]


def test_strategy_engines_use_same_contract_version():
    assert OpenReversalEngine.strategy_version == STRATEGY_VERSION
    assert GapExtensionReversalEngine.strategy_version == STRATEGY_VERSION


def test_contracts_are_the_authoritative_rule_source():
    assert strategy_metadata("STRATEGY_1")["version"] == STRATEGY_VERSION
    assert strategy_metadata("STRATEGY_2")["version"] == STRATEGY_VERSION
    assert len(strategy_metadata("STRATEGY_1")["rules"]) >= 4
    assert len(strategy_metadata("STRATEGY_2")["rules"]) >= 4


def test_strategy_1_signal_carries_identity():
    engine = OpenReversalEngine("09:45", "14:00", 1.25)
    signal = engine.build_signal("TEST", "BUY", 105.0, 105.0, 100.0, 95.0, 0.5)
    assert signal["strategy"] == "STRATEGY_1"
    assert signal["strategy_version"] == STRATEGY_VERSION


def test_strategy_2_signal_carries_identity():
    engine = GapExtensionReversalEngine("09:45", "14:00", 1.25)
    assert engine.strategy_id == "STRATEGY_2"
    assert engine.strategy_version == STRATEGY_VERSION


def test_dashboard_does_not_duplicate_strategy_rule_text():
    current = (ROOT / "dashboard" / "pages" / "current_trading.py").read_text(encoding="utf-8")
    analysis = (ROOT / "dashboard" / "pages" / "strategy2_analysis.py").read_text(encoding="utf-8")
    assert "strategy_metadata" in current
    assert "strategy_metadata" in analysis
    assert "Open > PDH → completed 1m close below PDH" not in current
    assert "Open < PDL → extension below Open" not in analysis


def test_scanner_uses_strategy_engine_for_initial_side():
    scanner = (ROOT / "scanner" / "scanner_engine.py").read_text(encoding="utf-8")
    assert "self.strategy.initial_side" in scanner
    assert 'row["OpeningSetup"] == "OPEN_ABOVE_PDH"' not in scanner
    assert 'row["OpeningSetup"] == "OPEN_BELOW_PDL"' not in scanner
