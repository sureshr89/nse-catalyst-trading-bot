"""Make the trading engine use the same authoritative Dhan snapshot as the dashboard."""

import pandas as pd


def _blocked(reason):
    return {
        "intraday": {}, "prices": pd.DataFrame(), "sector": {},
        "nifty_change": None, "ad_ratio": None, "ad_complete": False,
        "buy_alignment": False, "sell_alignment": False, "dhan_quotes": {},
        "block_reason": reason,
    }


def install(MasterEngine):
    if getattr(MasterEngine, "_authoritative_dhan_snapshot_installed", False):
        return MasterEngine
    original = MasterEngine._market_snapshot

    def snapshot(self):
        # The authoritative Dhan snapshot is the source of truth. The older
        # master snapshot is used only as a fallback for diagnostic context;
        # it must never survive as a tradable alignment when Dhan verification
        # fails.
        try:
            from market.nifty500_breadth import BREADTH
            authoritative = BREADTH.snapshot(force=False)
            complete = bool(authoritative.get("complete") and authoritative.get("sector_complete"))
            rows = authoritative.get("quote_rows")

            if not complete:
                reason = str(authoritative.get("reason") or "DHAN_VERIFICATION_FAILED")
                self.diagnostics.setdefault("rejections", {})["authoritative_snapshot"] = reason
                self.diagnostics.update({
                    "market_data_source": "DHAN_VERIFICATION_FAILED",
                    "market_snapshot": "BLOCKED",
                    "market_gate": "NO_ALIGNMENT",
                    "market_data_coverage": f"{authoritative.get('evaluated', 0)}/500",
                    "ad_coverage": f"{authoritative.get('evaluated', 0)}/500",
                    "sector_available": False,
                    "buy_alignment": False,
                    "sell_alignment": False,
                })
                snap = _blocked(reason)
                self.last_snapshot = snap
                return snap

            if not isinstance(rows, pd.DataFrame) or len(rows) != 500:
                reason = f"DHAN_QUOTE_ROWS_NOT_500_{len(rows) if isinstance(rows, pd.DataFrame) else 0}/500"
                self.diagnostics.setdefault("rejections", {})["authoritative_snapshot"] = reason
                self.diagnostics.update({
                    "market_data_source": "DHAN_VERIFICATION_FAILED",
                    "market_snapshot": "BLOCKED",
                    "market_gate": "NO_ALIGNMENT",
                    "market_data_coverage": reason,
                    "ad_coverage": reason,
                    "sector_available": False,
                    "buy_alignment": False,
                    "sell_alignment": False,
                })
                snap = _blocked(reason)
                self.last_snapshot = snap
                return snap

            n = authoritative.get("nifty500_change_pct")
            sector_pct = authoritative.get("sector_alignment_pct")
            ad = authoritative.get("ad_ratio")
            buy = bool(n is not None and sector_pct is not None and ad is not None and n > 0 and sector_pct > 0 and ad > 1)
            sell = bool(n is not None and sector_pct is not None and ad is not None and n < 0 and sector_pct < 0 and ad < 1)
            quotes = {str(r["Symbol"]).upper().strip(): r for r in rows.to_dict("records")}

            snap = {
                "intraday": getattr(self, "last_snapshot", {}).get("intraday", {}),
                "prices": rows[[c for c in ["Symbol", "LTP", "PreviousClose", "NetChange", "change_pct"] if c in rows.columns]].copy(),
                "sector": {
                    "available": True,
                    "alignment_pct": sector_pct,
                    "mapped": int(authoritative.get("sector_mapped", 0) or 0),
                    "priced": int(authoritative.get("sector_priced", 0) or 0),
                    "coverage": authoritative.get("sector_coverage", "500/500"),
                    "positive_sectors": int(authoritative.get("positive_sectors", 0) or 0),
                    "negative_sectors": int(authoritative.get("negative_sectors", 0) or 0),
                    "unchanged_sectors": int(authoritative.get("unchanged_sectors", 0) or 0),
                    "sectors": int(authoritative.get("sector_count", 0) or 0),
                },
                "nifty_change": float(n) if n is not None else None,
                "ad_ratio": float(ad) if ad is not None else None,
                "ad_complete": True,
                "buy_alignment": buy,
                "sell_alignment": sell,
                "dhan_quotes": quotes,
                "verified": authoritative,
            }
            self.last_snapshot = snap
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
                "stocks_scanned": 500,
            })
            return snap
        except Exception as exc:
            reason = f"AUTHORITATIVE_SNAPSHOT_ERROR_{type(exc).__name__}"
            self.diagnostics.setdefault("rejections", {})["authoritative_snapshot"] = reason
            self.diagnostics.update({"market_data_source": "DHAN_VERIFICATION_FAILED", "market_snapshot": "BLOCKED", "market_gate": "NO_ALIGNMENT", "buy_alignment": False, "sell_alignment": False})
            snap = _blocked(reason)
            self.last_snapshot = snap
            return snap

    MasterEngine._market_snapshot = snapshot
    MasterEngine._authoritative_dhan_snapshot_installed = True
    return MasterEngine
