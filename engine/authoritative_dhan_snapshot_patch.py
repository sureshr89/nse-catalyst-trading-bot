"""Make the trading engine use the same authoritative Dhan snapshot as the dashboard."""


def install(MasterEngine):
    if getattr(MasterEngine, "_authoritative_dhan_snapshot_installed", False):
        return MasterEngine
    original = MasterEngine._market_snapshot

    def snapshot(self):
        snap = original(self)
        try:
            from market.nifty500_breadth import BREADTH
            authoritative = BREADTH.snapshot(force=False)
            if not authoritative.get("complete") or not authoritative.get("sector_complete"):
                return snap
            rows = authoritative.get("quote_rows")
            quotes = {}
            if rows is not None and not rows.empty:
                quotes = {str(r["Symbol"]).upper(): r for r in rows.to_dict("records")}
            n = authoritative.get("nifty500_change_pct")
            sector_pct = authoritative.get("sector_alignment_pct")
            ad = authoritative.get("ad_ratio")
            buy = bool(n is not None and sector_pct is not None and ad is not None and n > 0 and sector_pct > 0 and ad > 1)
            sell = bool(n is not None and sector_pct is not None and ad is not None and n < 0 and sector_pct < 0 and ad < 1)
            snap.update({
                "nifty_change": n,
                "ad_ratio": ad,
                "ad_complete": True,
                "sector": {
                    "available": True,
                    "alignment_pct": sector_pct,
                    "mapped": authoritative.get("sector_mapped", 500),
                    "priced": authoritative.get("sector_priced", 500),
                    "coverage": authoritative.get("sector_coverage", "500/500"),
                    "positive_sectors": authoritative.get("positive_sectors", 0),
                    "negative_sectors": authoritative.get("negative_sectors", 0),
                    "unchanged_sectors": authoritative.get("unchanged_sectors", 0),
                    "sectors": authoritative.get("sector_count", 0),
                },
                "buy_alignment": buy,
                "sell_alignment": sell,
                "dhan_quotes": quotes,
            })
            self.diagnostics.update({
                "market_data_source": "DHAN_VERIFIED_500",
                "market_snapshot": "PASS",
                "market_gate": "BUY" if buy else "SELL" if sell else "NO_ALIGNMENT",
                "nifty500_change_pct": n,
                "sector_change_pct": sector_pct,
                "sector_available": True,
                "sector_mapping": "500/500",
                "sector_priced": "500/500",
                "ad_ratio": ad,
                "ad_advances": authoritative.get("advances", 0),
                "ad_declines": authoritative.get("declines", 0),
                "ad_coverage": "500/500",
                "buy_alignment": buy,
                "sell_alignment": sell,
                "market_data_coverage": "500/500",
            })
        except Exception as exc:
            self.diagnostics.setdefault("rejections", {})["authoritative_snapshot"] = f"{type(exc).__name__}: {exc}"
        return snap

    MasterEngine._market_snapshot = snapshot
    MasterEngine._authoritative_dhan_snapshot_installed = True
    return MasterEngine
