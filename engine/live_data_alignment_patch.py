"""Force S1-S5 master decisions to use the exact verified Dhan NIFTY 500 snapshot."""
import pandas as pd


def install(MasterEngine):
    original_snapshot = MasterEngine._market_snapshot

    def aligned_snapshot(self):
        # Keep the existing intraday candle setup engine, but replace every
        # market-gate value with the same verified Dhan snapshot shown by the
        # dashboard. This prevents Yahoo/index-path disagreement from blocking
        # or creating S1-S5 signals.
        base = original_snapshot(self)
        try:
            from market.nifty500_breadth import BREADTH
            verified = BREADTH.snapshot(force=False)
        except Exception:
            return base

        if not verified.get("complete") or not verified.get("sector_complete"):
            base.update({"ad_complete": False, "buy_alignment": False, "sell_alignment": False})
            self.diagnostics["market_data_source"] = "DHAN_VERIFICATION_FAILED"
            self.diagnostics["ad_coverage"] = f"{verified.get('evaluated',0)}/500"
            return base

        quotes = verified.get("quote_rows")
        if not isinstance(quotes, pd.DataFrame) or len(quotes) != 500:
            base.update({"ad_complete": False, "buy_alignment": False, "sell_alignment": False})
            self.diagnostics["market_data_source"] = "DHAN_VERIFICATION_FAILED"
            return base

        # Use exactly the values driving the dashboard: Dhan LTP vs Dhan
        # previous-close/net-change for all 500 stocks.
        prices = quotes[[c for c in ["Symbol", "LTP", "PreviousClose", "NetChange", "change_pct"] if c in quotes.columns]].copy()
        if "change_pct" not in prices.columns:
            prices["change_pct"] = (prices["LTP"] - prices["PreviousClose"]) / prices["PreviousClose"] * 100

        sector = {
            "available": True,
            "mapped": int(verified.get("sector_mapped", 500) or 0),
            "priced": int(verified.get("sector_priced", 500) or 0),
            "coverage": str(verified.get("sector_coverage", "500/500")),
            "alignment_pct": verified.get("sector_alignment_pct"),
            "positive_sectors": verified.get("positive_sectors", 0),
            "negative_sectors": verified.get("negative_sectors", 0),
            "unchanged_sectors": verified.get("unchanged_sectors", 0),
        }
        nifty_change = verified.get("nifty500_change_pct")
        ad_ratio = verified.get("ad_ratio")
        advances = int(verified.get("advances", 0) or 0)
        declines = int(verified.get("declines", 0) or 0)
        sector_change = sector.get("alignment_pct")
        buy = bool(nifty_change is not None and float(nifty_change) > 0 and sector_change is not None and float(sector_change) > 0 and ad_ratio is not None and float(ad_ratio) > 1)
        sell = bool(nifty_change is not None and float(nifty_change) < 0 and sector_change is not None and float(sector_change) < 0 and ad_ratio is not None and float(ad_ratio) < 1)

        # Dhan live prices become authoritative for every stock's entry/exit
        # value and for today's live OHLC used by the strategy.
        dhan_quotes = {str(r["Symbol"]).upper(): r for r in quotes.to_dict("records")}
        base.update({
            "prices": prices,
            "sector": sector,
            "nifty_change": float(nifty_change) if nifty_change is not None else None,
            "ad_ratio": float(ad_ratio) if ad_ratio is not None else None,
            "ad_complete": True,
            "buy_alignment": buy,
            "sell_alignment": sell,
            "dhan_quotes": dhan_quotes,
        })
        self.diagnostics.update({
            "market_data_source": "DHAN_VERIFIED_500",
            "market_data_coverage": "500/500",
            "nifty500_change_pct": nifty_change,
            "sector_change_pct": sector_change,
            "sector_available": True,
            "sector_mapping": f"{sector['mapped']}/500",
            "sector_priced": f"{sector['priced']}/500",
            "ad_ratio": ad_ratio,
            "ad_advances": advances,
            "ad_declines": declines,
            "ad_coverage": "500/500",
            "buy_alignment": buy,
            "sell_alignment": sell,
        })
        return base

    MasterEngine._market_snapshot = aligned_snapshot
    return MasterEngine
