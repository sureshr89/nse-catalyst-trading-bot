import pandas as pd


def _mapping(n=200):
    return pd.DataFrame({"Symbol":[f"S{i}" for i in range(n)],"SecurityId":[str(1000+i) for i in range(n)]})


def _response(ids):
    data={}
    for sid in ids:
        p=100.0+int(sid)%10
        data[str(sid)]={"last_price":p,"volume":1000,"ohlc":{"open":p-1,"high":p+1,"low":p-2,"close":p-2}}
    return {"data":{"NSE_EQ":data}}


def test_collection_merges_batches_without_requiring_one_500_row_response(monkeypatch):
    import market.live_quote_bridge as bridge
    bridge._CACHE_ROWS=pd.DataFrame();bridge._CACHE_KEY=None;bridge._CACHE_AT=0.0
    calls=[]
    def fake_marketfeed(segment,ids,endpoint):
        calls.append(list(ids))
        return _response(ids)
    monkeypatch.setattr(bridge.dhan_data,"configured",lambda:True)
    monkeypatch.setattr(bridge.dhan_data,"_marketfeed",fake_marketfeed)
    result=bridge.market_quote_partial(_mapping(200))
    assert len(result)==200
    assert set(result["Symbol"])=={f"S{i}" for i in range(200)}
    assert len(calls)==2


def test_collection_cache_reuses_same_snapshot(monkeypatch):
    import market.live_quote_bridge as bridge
    bridge._CACHE_ROWS=pd.DataFrame();bridge._CACHE_KEY=None;bridge._CACHE_AT=0.0
    calls=[]
    monkeypatch.setattr(bridge.dhan_data,"configured",lambda:True)
    monkeypatch.setattr(bridge.dhan_data,"_marketfeed",lambda s,ids,e:(calls.append(ids) or _response(ids)))
    mapping=_mapping(100)
    first=bridge.market_quote_partial(mapping)
    second=bridge.market_quote_partial(mapping)
    assert len(first)==len(second)==100
    assert len(calls)==1
