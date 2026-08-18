from strategy import open_reversal_engine as module
from strategy.open_reversal_engine import OpenReversalEngine


class FakeLive:
    def __init__(self, price):
        self.price = float(price)

    def get_latest_live_price(self, symbol, max_age_seconds=2):
        return {"Close": self.price}


def test_s1_buy_does_not_qualify_without_pdh_touch(monkeypatch):
    fake = FakeLive(106.0)
    monkeypatch.setattr(module, "_LIVE", fake)
    engine = OpenReversalEngine("00:00", "23:59", 1.25)
    state = {"symbol": "TEST", "side": "BUY", "pdh_breached": False, "open_returned": False}

    state = engine.update_state(state, 105.0, 100.0, 95.0)
    assert state.get("pdh_breached") is False
    assert state.get("open_returned") is False

    fake.price = 99.5
    state = engine.update_state(state, 105.0, 100.0, 95.0)
    assert state.get("pdh_breached") is True
    assert state.get("open_returned") is False

    fake.price = 105.0
    state = engine.update_state(state, 105.0, 100.0, 95.0)
    assert state.get("open_returned") is True


def test_s1_sell_does_not_qualify_without_pdl_touch(monkeypatch):
    fake = FakeLive(89.0)
    monkeypatch.setattr(module, "_LIVE", fake)
    engine = OpenReversalEngine("00:00", "23:59", 1.25)
    state = {"symbol": "TEST", "side": "SELL", "pdl_breached": False, "open_returned": False}

    state = engine.update_state(state, 90.0, 105.0, 100.0)
    assert state.get("pdl_breached") is False
    assert state.get("open_returned") is False

    fake.price = 100.5
    state = engine.update_state(state, 90.0, 105.0, 100.0)
    assert state.get("pdl_breached") is True
    assert state.get("open_returned") is False

    fake.price = 90.0
    state = engine.update_state(state, 90.0, 105.0, 100.0)
    assert state.get("open_returned") is True
