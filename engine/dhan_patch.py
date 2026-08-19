"""Small compatibility patch that makes the existing S1-S5 engine use Dhan
for the master NIFTY 500 / sector / A-D gates without rewriting the strategy
state machine. The strategy candle layer remains unchanged until its dedicated
Dhan intraday-feed integration is completed.
"""
from market.dhan_data import configured as dhan_configured
from market.nifty500_breadth import BREADTH


def install(MasterEngine):
    if getattr(MasterEngine, "_dhan_gate_patch_installed", False):
        return MasterEngine
    original = MasterEngine._market_snapshot

    def _market_snapshot(self):
        base = original(self)
        if not dhan_configured():
            return base
        try:
            breadth = BREADTH.snapshot()
            if not breadth.get("complete"):
                self.diagnostics["rejections"]["dhan_breadth"] = breadth.get("reason", "DHAN_BREADTH_UNAVAILABLE")
                return base
            nifty = breadth.get("nifty500_change_pct")
            sector = breadth.get("sector_alignment_pct")
            ad_ratio = breadth.get("ad_ratio")
            sector_ok = bool(breadth.get("sector_complete"))
            buy = bool(nifty is not None and nifty > 0 and sector_ok and sector is not None and sector > 0 and ad_ratio is not None and ad_ratio > 1)
            sell = bool(nifty is not None and nifty < 0 and sector_ok and sector is not None and sector < 0 and ad_ratio is not None and ad_ratio < 1)
            base.update({
                "nifty_change": nifty,
                "ad_ratio": ad_ratio,
                "ad_complete": True,
                "buy_alignment": buy,
                "sell_alignment": sell,
            })
            base["sector"] = {
                "available": sector_ok,
                "alignment_pct": sector,
                "mapped": breadth.get("sector_mapped", 0),
                "priced": breadth.get("sector_priced", 0),
                "coverage": breadth.get("sector_coverage", "0/500"),
                "sectors": breadth.get("sector_count", 0),
                "positive_sectors": breadth.get("positive_sectors", 0),
                "negative_sectors": breadth.get("negative_sectors", 0),
            }
            self.diagnostics.update({
                "nifty500_change_pct": nifty,
                "sector_change_pct": sector,
                "sector_available": sector_ok,
                "sector_mapping": f"{breadth.get('sector_mapped', 0)}/500",
                "sector_priced": f"{breadth.get('sector_priced', 0)}/500",
                "ad_ratio": ad_ratio,
                "ad_advances": breadth.get("advances", 0),
                "ad_declines": breadth.get("declines", 0),
                "ad_coverage": "500/500",
                "buy_alignment": buy,
                "sell_alignment": sell,
                "market_data_source": "DHAN",
            })
            self.diagnostics["rejections"].pop("dhan_breadth", None)
            return base
        except Exception as exc:
            self.diagnostics["rejections"]["dhan_breadth"] = f"DHAN_BREADTH_ERROR_{type(exc).__name__}"
            return base

    MasterEngine._market_snapshot = _market_snapshot
    MasterEngine._dhan_gate_patch_installed = True
    return MasterEngine
