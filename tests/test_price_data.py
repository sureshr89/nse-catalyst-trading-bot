import pandas as pd
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from market.price_data import PriceData
IST=ZoneInfo("Asia/Kolkata")

def test_daily_period_parses_numeric_days():
    pd_obj=PriceData();calls={};mapping=pd.DataFrame([{"Symbol":"ABC","SecurityId":"123"}])
    def fake_history(sid,start,end): calls["start"]=start;calls["end"]=end;return pd.DataFrame()
    with patch.object(pd_obj,"_map",return_value=mapping),patch("market.dhan_data.daily_history",fake_history),patch("market.dhan_data.configured",return_value=True): pd_obj.get_daily("ABC","10d")
    start=datetime.fromisoformat(calls["start"]).date();end=datetime.fromisoformat(calls["end"]).date();assert (end-start).days==16

def test_completed_excludes_current_minute():
    now=datetime.now(IST).replace(second=0,microsecond=0);frame=pd.DataFrame([{ "Datetime":now,"Open":100,"High":101,"Low":99,"Close":100},{"Datetime":now.replace(minute=max(0,now.minute-1)),"Open":100,"High":101,"Low":99,"Close":100}]);result=PriceData._completed(frame);assert all(result["Datetime"]<now)

def test_live_price_uses_dhan_source_label():
    pd_obj=PriceData();pd_obj._live_price_cache.clear();pd_obj._live_price_cache_at.clear()
    mapping=pd.DataFrame([{"Symbol":"ABC","SecurityId":"123"}])
    quote=pd.DataFrame([{ "Symbol":"ABC","LTP":110,"TodayOpen":108,"TodayHigh":112,"TodayLow":107,"PreviousClose":105,"NetChange":5}])
    with patch("market.dhan_data.configured",return_value=True) as configured_mock, patch("market.dhan_data.map_nifty500",return_value=mapping) as map_mock, patch("market.dhan_data.market_quote",return_value=quote) as quote_mock:
        result=pd_obj.get_latest_live_price("ABC",max_age_seconds=0)
    configured_mock.assert_called_once()
    map_mock.assert_called_once_with(["ABC"])
    quote_mock.assert_called_once()
    assert result is not None
    assert result["price_source"]=="DHAN_OHLC"
    assert result["Close"]==110.0
