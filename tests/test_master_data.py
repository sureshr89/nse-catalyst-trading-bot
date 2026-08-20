import pandas as pd
import master_data


def test_prune_to_last_six_months(tmp_path, monkeypatch):
    path = tmp_path / "master.csv"
    frame = pd.DataFrame({"TradeDate": ["2025-01-01", "2026-03-01", "2026-08-01"], "value": [1, 2, 3]})
    frame.to_csv(path, index=False)
    monkeypatch.setattr(master_data, "MASTER_MONTHS", 6)
    master_data._prune_to_last_six_months(path, ["TradeDate"])
    result = pd.read_csv(path)
    assert "2025-01-01" not in result["TradeDate"].tolist()
    assert "2026-03-01" in result["TradeDate"].tolist()
    assert "2026-08-01" in result["TradeDate"].tolist()


def test_merge_deduplicates_authoritative_keys(tmp_path, monkeypatch):
    path = tmp_path / "master.csv"
    pd.DataFrame({"TradeDate": ["2026-08-20"], "Symbol": ["ABC"], "value": [1]}).to_csv(path, index=False)
    monkeypatch.setattr(master_data, "_read", lambda p: pd.read_csv(p) if p.exists() else pd.DataFrame())
    master_data._merge(path, pd.DataFrame({"TradeDate": ["2026-08-20"], "Symbol": ["ABC"], "value": [2]}), ["TradeDate", "Symbol"])
    result = pd.read_csv(path)
    assert len(result) == 1
    assert int(result.iloc[0]["value"]) == 2


def test_authoritative_master_paths_are_outputs():
    assert master_data.MASTER_STOCK.parent.name == "outputs"
    assert master_data.MASTER_TRADES.parent.name == "outputs"
    assert master_data.MASTER_DAILY.parent.name == "outputs"
