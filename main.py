"""Canonical NSE Catalyst production entrypoint.

The dashboard imports ``MasterEngine`` from this module, so this file is kept
small and deliberately contains no duplicate market-data or strategy logic.
"""
from engine.master_engine import MasterEngine as _MasterEngine
from engine.cycle_runner import run_cycle as _run_cycle


class MasterEngine(_MasterEngine):
    """Dashboard-facing engine using the canonical production cycle."""

    def _publish_dashboard_snapshot(self):
        """Expose the exact verified engine snapshot to the existing dashboard.

        The presentation layer historically queried the legacy breadth provider
        separately.  That could make the dashboard show different A/D/sector
        values from the values actually used by the trading engine.  This bridge
        keeps the existing UI intact while making both layers consume one source
        of truth.
        """
        try:
            from market.nifty500_breadth import BREADTH

            snap = self.last_snapshot if isinstance(self.last_snapshot, dict) else {}
            prices = snap.get("prices")
            sector = snap.get("sector") or {}
            if prices is None or not hasattr(prices, "copy"):
                return

            prices = prices.copy()
            if "Symbol" in prices.columns:
                prices["Symbol"] = prices["Symbol"].astype(str).str.upper().str.strip()

            # The dashboard expects constituent rows.  Only verified/live rows
            # are published; coverage remains the real value (>=475, not padded).
            complete = bool(snap.get("verified")) and int(len(prices)) >= 475
            ad_ratio = snap.get("ad_ratio")
            advances = int((prices["change_pct"] > 0).sum()) if "change_pct" in prices.columns else 0
            declines = int((prices["change_pct"] < 0).sum()) if "change_pct" in prices.columns else 0
            unchanged = int((prices["change_pct"] == 0).sum()) if "change_pct" in prices.columns else 0
            positive_sectors = int(sector.get("positive_sectors", 0) or 0)
            negative_sectors = int(sector.get("negative_sectors", 0) or 0)
            coverage = len(prices)

            dashboard_snapshot = {
                "complete": complete,
                "sector_complete": bool(sector.get("available")) and int(sector.get("priced", 0) or 0) >= 475,
                "evaluated": coverage,
                "sector_priced": int(sector.get("priced", 0) or 0),
                "nifty500_change_pct": snap.get("nifty_change"),
                "ad_ratio": ad_ratio,
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "positive_sectors": positive_sectors,
                "negative_sectors": negative_sectors,
                "quote_rows": prices,
                "reason": "" if complete else self.diagnostics.get("rejections", {}).get("market_data", "NIFTY 500 coverage below 95%"),
                "nifty500_ltp": None,
                "nifty500_net_change": None,
                "nifty500_previous_close": None,
                "nifty500_index_source": "Dhan / production engine",
            }

            def _snapshot(force=False):
                return dashboard_snapshot

            BREADTH.snapshot = _snapshot
        except Exception:
            # Dashboard presentation must never break the production trading path.
            return

    def run_cycle(self):
        result = _run_cycle(self)
        self._publish_dashboard_snapshot()
        return result


TradingBot = MasterEngine
__all__ = ["TradingBot", "MasterEngine", "build_engine"]


def build_engine():
    """Create the same engine instance used by the Streamlit application."""
    return MasterEngine()


if __name__ == "__main__":
    # Preserve the existing direct-entry dashboard behavior.
    from dashboard.tabbed_app import render_dashboard
    render_dashboard()
