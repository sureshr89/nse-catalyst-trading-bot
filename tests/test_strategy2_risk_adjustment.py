from strategy2_runtime import Strategy2Runtime


class _Paper:
    available_capital = 250000.0


def _runtime():
    runtime = object.__new__(Strategy2Runtime)
    runtime.paper_engine = _Paper()
    runtime.diagnostics = {"risk_adjusted": 0, "rejections": {}}
    return runtime


def test_tight_sell_stop_is_widened_to_about_1450_risk():
    runtime = _runtime()
    signal = {
        "symbol": "UNOMINDA",
        "signal": "SELL",
        "entry": 1270.8,
        "stop_loss": 1274.7,
        "target": 1246.9,
    }
    assert runtime._normalize_risk(signal) is True
    assert signal["risk_adjusted"] is True
    assert signal["original_stop_loss"] == 1274.7
    assert 1400 <= signal["estimated_risk"] <= 1500
    assert abs(signal["estimated_risk"] - 1450) <= 0.01
    assert signal["stop_loss"] > signal["original_stop_loss"]
    assert signal["risk_reward"] >= 1.25


def test_tight_buy_stop_is_widened_to_about_1450_risk():
    runtime = _runtime()
    signal = {
        "symbol": "TEST",
        "signal": "BUY",
        "entry": 93.0,
        "stop_loss": 92.9,
        "target": 100.0,
    }
    assert runtime._normalize_risk(signal) is True
    assert signal["risk_adjusted"] is True
    assert 1400 <= signal["estimated_risk"] <= 1500
    assert abs(signal["estimated_risk"] - 1450) <= 0.01
    assert signal["stop_loss"] < signal["original_stop_loss"]
    assert signal["risk_reward"] >= 1.25


def test_stop_already_in_risk_band_is_not_changed():
    runtime = _runtime()
    signal = {
        "symbol": "PCBL",
        "signal": "SELL",
        "entry": 320.55,
        "stop_loss": 322.8,
        "target": 317.2,
    }
    assert runtime._normalize_risk(signal) is True
    assert signal["risk_adjusted"] is False
    assert signal["stop_loss"] == 322.8
    assert signal["original_stop_loss"] == 322.8
