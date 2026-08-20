import pandas as pd
from engine.master_engine import MasterEngine


def test_master_engine_starts_blocked_until_verified():
    engine = object.__new__(MasterEngine)
    diag = engine._blank_diag()
    assert diag['market_data_source'] == 'DHAN_ONLY'
    assert diag['trade_path_status'] == 'BLOCKED'
    assert diag['market_data_coverage'] == '0/500'


def test_incomplete_reference_universe_cannot_become_ready():
    engine = object.__new__(MasterEngine)
    engine._session_date = None
    engine.references = pd.DataFrame()
    engine.sector_map = pd.DataFrame()
    engine.diagnostics = engine._blank_diag()
    class U:
        def get_dataframe(self, refresh=False):
            return pd.DataFrame({'Symbol': ['A']})
    engine.universe_engine = U()
    engine._refresh_reference_data(True)
    assert engine.references.empty
    assert engine.diagnostics['trade_path_status'] == 'BLOCKED'
