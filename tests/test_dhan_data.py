import pandas as pd
import market.dhan_data as dd


def test_nifty500_index_quote_does_not_use_hardcoded_id(monkeypatch):
    master = pd.DataFrame({
        "SEM_TRADING_SYMBOL": ["NIFTY 500"],
        "SEM_SMST_SECURITY_ID": [999],
        "SEM_SEGMENT": ["I"],
        "SEM_EXM_EXCH_ID": ["NSE"],
        "SEM_INSTRUMENT_NAME": ["INDEX"],
    })
    monkeypatch.setattr(dd, "load_instrument_master", lambda force=False: master)
    seen = {}

    def fake_post(path, payload, timeout=15):
        seen["payload"] = payload
        return {"data": {"IDX_I": {"999": {"last_price": 25000, "net_change": 100}}}}

    monkeypatch.setattr(dd, "configured", lambda: True)
    monkeypatch.setattr(dd, "_post", fake_post)
    result = dd.index_quote("NIFTY 500")
    assert result is not None
    assert result["SecurityId"] == "999"
    # Dhan market-feed payloads use numeric security IDs.  The response keys
    # remain strings, so the production adapter normalizes only at the boundary.
    assert seen["payload"] == {"IDX_I": [999]}


def test_nifty500_mapping_failure_returns_none(monkeypatch):
    monkeypatch.setattr(dd, "configured", lambda: True)
    monkeypatch.setattr(dd, "load_instrument_master", lambda force=False: pd.DataFrame())
    assert dd.index_quote("NIFTY 500") is None


def test_equity_quote_rejects_incomplete_batch(monkeypatch):
    mapping = pd.DataFrame({"Symbol": ["ABC", "XYZ"], "SecurityId": [1, 2]})
    monkeypatch.setattr(dd, "configured", lambda: True)
    monkeypatch.setattr(dd, "_marketfeed", lambda *args, **kwargs: {"data": {"NSE_EQ": {"1": {"last_price": 110, "net_change": 1, "ohlc": {"open": 109, "high": 111, "low": 108, "close": 109}, "volume": 100}}}})
    assert dd.market_quote(mapping).empty
