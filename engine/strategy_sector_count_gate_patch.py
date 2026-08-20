"""Make the S1-S5 market gate use the verified sector counts.

The dashboard's authoritative Dhan snapshot reports positive/negative sector
counts. Strategy gating uses those same counts; the displayed aggregate
sector percentage remains unchanged.
"""


def install(MasterEngine):
    if getattr(MasterEngine, "_strategy_sector_count_gate_installed", False):
        return MasterEngine
    original = MasterEngine._evaluate_stock

    def _evaluate_stock(self, symbol, ref, d, snap):
        sector = dict(snap.get("sector") or {})
        positive = int(sector.get("positive_sectors", 0) or 0)
        negative = int(sector.get("negative_sectors", 0) or 0)
        nifty = snap.get("nifty_change")
        ad = snap.get("ad_ratio")
        buy = bool(nifty is not None and float(nifty) > 0 and ad is not None and float(ad) > 1 and positive > negative)
        sell = bool(nifty is not None and float(nifty) < 0 and ad is not None and float(ad) < 1 and negative > positive)
        sector["alignment_pct"] = 1.0 if positive > negative else -1.0 if negative > positive else 0.0
        local = dict(snap)
        local["sector"] = sector
        local["buy_alignment"] = buy
        local["sell_alignment"] = sell
        return original(self, symbol, ref, d, local)

    MasterEngine._evaluate_stock = _evaluate_stock
    MasterEngine._strategy_sector_count_gate_installed = True
    return MasterEngine
