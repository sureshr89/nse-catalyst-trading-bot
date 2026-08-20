import pandas as pd
import market.dhan_data as d

def test_dhan_mapping_returns_requested_symbols_only(monkeypatch):
    master=pd.DataFrame({'SEM_TRADING_SYMBOL':['ABC','XYZ'],'SEM_SMST_SECURITY_ID':['123','456'],'SEM_SEGMENT':['E','E'],'SEM_EXM_EXCH_ID':['NSE','NSE'],'SEM_SERIES':['EQ','EQ']})
    monkeypatch.setattr(d,'load_instrument_master',lambda force=False:master)
    out=d.map_nifty500(['ABC'])
    assert list(out['Symbol'])==['ABC']
    assert list(out['SecurityId'])==['123']
