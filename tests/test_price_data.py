import pandas as pd
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from market.price_data import PriceData
import market.price_data as price_data_module

IST=ZoneInfo("Asia/Kolkata")

def test_daily_period_parses_numeric_days():
    pd_obj=PriceData();calls={}
    mapping=pd.DataFrame([{"Symbol":"ABC","SecurityId":"123"}])
    def fake_history(sid,start,end): calls["start"]=start;calls["end"]=end;return pd.DataFrame()
    with patch.object(price_data_module.dhan_data,"map_nifty500",return_value=mapping),patch.object(price_data_module.dhan_data,"daily_history",fake_history),patch.object(price_data_module.dhan_data,"configured",return_value=True):
        pd_obj.get_daily("ABC","10d")
    start=datetime.fromisoformat(calls["start"]).date();end=datetime.fromisoformat(calls["end"]).date();assert (end-start).days==16

def test_completed_excludes_current_minute():
    now=datetime.now(IST).replace(second=0,microsecond=0)
    frame=pd.DataFrame([{"Datetime":now,"Open":100,"High":101,"Low":99,"Close":100},{"Datetime":now.replace(minute=max(0,now.minute-1)),"Open":100,"High":101,"Low":99,"Close":100}])
    result=PriceData._completed(frame)
    assert all(result["Datetime"]<now)

def test_live_price_uses_dhan_source_label():
    """Verify PriceData's Dhan quote normalization without relying on module identity."""
    symbol="PRICE_TEST_UNIQUE"
    PriceData._live_price_cache.pop(symbol,None);PriceData._live_price_cache_at.pop(symbol,None)
    pd_obj=PriceData()
    mapping=pd.DataFrame([{"Symbol":symbol,"SecurityId":"123"}])
    quote=pd.DataFrame([{"SecurityId":"123","Symbol":symbol,"LTP":110,"TodayOpen":108,"TodayHigh":112,"TodayLow":107,"PreviousClose":105,"NetChange":5}])

    # Patch the exact instance boundary used by this behavioral test.  The
    # production implementation remains Dhan-only; the test must not depend
    # on whether another test imported market.dhan_data through a second
    # module reference in the same pytest process.
    with patch.object(pd_obj,"_map",return_value=mapping), \
         patch.object(pd_obj, "_dhan_configured", return_value=True), \
         patch.object(pd_obj, "_dhan_market_quote", return_value=quote):
        result=pd_obj.get_latest_live_price(symbol,max_age_seconds=0)

    assert result is not None
    assert result["price_source"]=="DHAN_OHLC"
    assert result["Close"]==110.0
    assert result["Open"]==108.0
    assert result["High"]==112.0
    assert result["Low"]==107.0
    assert result["PreviousClose"]==105.0
    assert result["NetChange"]==5.0
