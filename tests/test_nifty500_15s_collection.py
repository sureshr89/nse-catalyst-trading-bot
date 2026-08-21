import pandas as pd


def _mapping(n=500):
    return pd.DataFrame({"Symbol":[f"S{i}" for i in range(n)],"SecurityId":[str(1000+i) for i in range(n)]})


def _response(ids):
    data={}
    for sid in ids:
        p=100.0+int(sid)%10
        data[str(sid)]={"last_price":p,"volume":1000,"ohlc":{"open":p-1,"high":p+1,"low":p-2,"close":p-2}}
    return {"data":{"NSE_EQ":data}}


def test_collection_merges_batches_and_accepts_only_at_least_490_fresh_rows(monkeypatch):
    import market.live_quote_bridge as bridge
    bridge._CACHE_ROWS=pd.DataFrame();bridge._CACHE_KEY=None;bridge._CACHE_AT=0.0
    calls=[]

    def fake_post(path,payload,timeout=15):
        ids=list(payload["NSE_EQ"])
        calls.append(ids)
        if len(calls)==1:
            ids=ids[:300]
        return _response(ids)

    monkeypatch.setattr(bridge.dhan_data,"configured",lambda:True)
    monkeypatch.setattr(bridge.dhan_data,"_post",fake_post)
    result=bridge.market_quote_partial(_mapping(500))
    assert len(result)==500
    assert set(result["Symbol"])=={f"S{i}" for i in range(500)}
    assert len(calls)==2


def test_collection_does_not_reuse_stale_snapshot_as_a_new_cycle(monkeypatch):
    import market.live_quote_bridge as bridge
    bridge._CACHE_ROWS=pd.DataFrame();bridge._CACHE_KEY=None;bridge._CACHE_AT=0.0
    calls=[]
    monkeypatch.setattr(bridge.dhan_data,"configured",lambda:True)
    monkeypatch.setattr(bridge.dhan_data,"_post",lambda path,payload,timeout=15:(calls.append(list(payload["NSE_EQ"])) or _response(payload["NSE_EQ"])))
    mapping=_mapping(500)
    first=bridge.market_quote_partial(mapping)
    second=bridge.market_quote_partial(mapping)
    assert len(first)==len(second)==500
    assert len(calls)==2
