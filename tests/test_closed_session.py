import pandas as pd
import market.closed_session as cs

def test_incomplete_universe_is_rejected(monkeypatch):
    class U:
        def get_dataframe(self, refresh=False):
            return pd.DataFrame({'Symbol':['A','B'],'Sector':['X','Y']})
    monkeypatch.setattr(cs, 'StockUniverse', lambda: U())
    monkeypatch.setattr(cs.BREADTH, 'snapshot', lambda force=False: {'complete': False})
    _, result = cs.build_closed_snapshot(force=True)
    assert result['complete'] is False
    assert 'NIFTY_500_UNIVERSE' in result['reason']
    assert result['coverage'] == '2/500'

def test_session_date_skips_weekend():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    d = cs._session_date(datetime(2026, 8, 22, 12, 0, tzinfo=ZoneInfo('Asia/Kolkata')))
    assert d.weekday() == 4
