import pandas as pd
from engine.master_engine import MasterEngine


def test_incomplete_nifty500_universe_is_blocked(monkeypatch):
    engine = object.__new__(MasterEngine)
    engine._session_date = None
    engine.references = pd.DataFrame()
    engine.sector_map = pd.DataFrame()
    engine.diagnostics = engine._blank_diag()
    class U:
        def get_dataframe(self, refresh=False):
            return pd.DataFrame({'Symbol':['A','B']})
    engine.universe_engine = U()
    monkeypatch.setattr('engine.master_engine.ReferenceStore', lambda u: pd.DataFrame())
    engine._refresh_reference_data(True)
    assert engine.references.empty
    assert 'NIFTY500_UNIVERSE_INCOMPLETE_2/500' in engine.diagnostics['rejections']['universe']


def test_incomplete_market_snapshot_is_blocked(monkeypatch):
    engine = object.__new__(MasterEngine)
    engine.references = pd.DataFrame({'Symbol':['A']})
    engine.sector_map = pd.DataFrame()
    engine.diagnostics = engine._blank_diag()
    monkeypatch.setattr('engine.master_engine.configured', lambda: True)
    result = engine._market_snapshot()
    assert result['verified'] is False
    assert engine.diagnostics['rejections']['market_data'] == 'DHAN_OR_REFERENCE_OR_SECTOR_UNAVAILABLE'
