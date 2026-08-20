"""Make the S1-S5 market gate use the verified sector counts.

The dashboard's authoritative Dhan snapshot reports positive/negative sector
counts. Strategy gating should use those same counts rather than a second
aggregate sector percentage calculation. The displayed sector percentage is
left unchanged.
"""


def install(MasterEngine):
    if getattr(MasterEngine, "_strategy_sector_count_gate_installed", False):
        return MasterEngine
    original = MasterEngine._evaluate_stock

    def _evaluate_stock(self, symbol, ref, d, snap):
        sector = dict(snap.get("sector") or {})
        positive = int(sector.get("positive_sectors", 0) or 0)
        negative = int(sector.get("negative_sectors", 0) or 0)
        if positive > negative:
            sector["alignment_pct"] = 1.0
        elif negative > positive:
            sector["alignment_pct"] = -1.0
        else:
            sector["alignment_pct"] = 0.0
        local = dict(snap)
        local["sector"] = sector
        return original(self, symbol, ref, d, local)

    MasterEngine._evaluate_stock = _evaluate_stock
    MasterEngine._strategy_sector_count_gate_installed = True
    return MasterEngine
