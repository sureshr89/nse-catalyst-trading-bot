"""Runtime resilience and fast authoritative NIFTY-500 Dhan market gate.

Dashboard/UI and S1-S5 definitions are untouched. Dhan NIFTY-500 breadth/sector
is acquired with short bounded retries and then injected into the master gate.
Partial data is never treated as valid A/D or sector alignment.
"""
from __future__ import annotations
import time


def fast_dhan_breadth_snapshot(max_attempts=5, delay_seconds=2.0):
    try:
        from market.nifty500_breadth import BREADTH
    except Exception:
        return None
    last = None
    for attempt in range(max_attempts):
        try:
            last = BREADTH.snapshot(force=True)
            if (last.get("complete") and last.get("sector_complete") and
                int(last.get("evaluated", 0)) == 500 and
                int(last.get("sector_mapped", 0)) == 500 and
                int(last.get("sector_priced", 0)) == 500):
                return last
        except Exception:
            last = None
        if attempt < max_attempts - 1:
            time.sleep(delay_seconds)
    return last


def install(MasterEngine):
    if getattr(MasterEngine, "_stability_patch_installed", False):
        return MasterEngine

    original_run_cycle = MasterEngine.run_cycle
    original_market_snapshot = MasterEngine._market_snapshot

    def market_snapshot(self):
        # Dhan is authoritative for NIFTY-500 A/D + sector. Try quickly before
        # the normal snapshot so a temporary partial response does not wait a
        # full one-minute cycle.
        dhan_snap = fast_dhan_breadth_snapshot(max_attempts=5, delay_seconds=2.0)
        base = original_market_snapshot(self)
        if not isinstance(base, dict):
            base = {}
        if dhan_snap and dhan_snap.get("complete") and dhan_snap.get("sector_complete"):
            ad = dhan_snap.get("ad_ratio")
            sec = dhan_snap.get("sector_alignment_pct")
            nifty = dhan_snap.get("nifty500_change_pct")
            base["ad_ratio"] = ad
            base["ad_complete"] = True
            base["nifty_change"] = nifty
            base["sector"] = {
                "available": True,
                "alignment_pct": sec,
                "mapped": 500,
                "priced": 500,
                "coverage": "500/500",
                "sectors": dhan_snap.get("sector_count", 0),
                "positive_sectors": dhan_snap.get("positive_sectors", 0),
                "negative_sectors": dhan_snap.get("negative_sectors", 0),
            }
            base["buy_alignment"] = bool(nifty is not None and nifty > 0 and sec is not None and sec > 0 and ad is not None and ad > 1)
            base["sell_alignment"] = bool(nifty is not None and nifty < 0 and sec is not None and sec < 0 and ad is not None and ad < 1)
            self.diagnostics.update({
                "market_data_source": "DHAN_NIFTY500",
                "market_data_coverage": "500/500",
                "ad_coverage": "500/500",
                "ad_ratio": ad,
                "ad_advances": dhan_snap.get("advances", 0),
                "ad_declines": dhan_snap.get("declines", 0),
                "sector_available": True,
                "sector_mapping": "500/500",
                "sector_priced": "500/500",
                "sector_change_pct": sec,
                "nifty500_change_pct": nifty,
            })
        else:
            # Do not allow the fallback Yahoo calculation to become an
            # apparently valid Dhan market gate.
            base["ad_complete"] = False
            base["ad_ratio"] = None
            base["buy_alignment"] = False
            base["sell_alignment"] = False
            base["sector"] = {"available": False, "alignment_pct": None, "mapped": 0, "priced": 0, "coverage": "0/500"}
            self.diagnostics["market_data_source"] = "DHAN_NIFTY500_WAITING"
        return base

    def run_cycle(self):
        try:
            return original_run_cycle(self)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            try:
                diagnostics = getattr(self, "diagnostics", None)
                if isinstance(diagnostics, dict):
                    diagnostics["runtime_error"] = message
                    diagnostics["runtime_error_at"] = self.now().isoformat(timespec="seconds")
                    diagnostics.setdefault("rejections", {})["runtime"] = message
                    writer = getattr(self, "_write_diagnostics", None)
                    if callable(writer): writer()
            except Exception:
                pass
            return []

    MasterEngine._market_snapshot = market_snapshot
    MasterEngine.run_cycle = run_cycle
    MasterEngine._stability_patch_installed = True
    return MasterEngine


def install_dhan_retry():
    """Retry only transient Dhan failures; never retry permanently invalid responses."""
    try:
        import market.dhan_data as dhan
    except Exception:
        return
    if getattr(dhan, "_retry_patch_installed", False):
        return
    original_post = dhan._post
    def post(path, payload, timeout=15):
        for attempt in range(3):
            result = original_post(path, payload, timeout=timeout)
            status = dhan.dhan_status(); http=status.get("http_status"); msg=str(status.get("message", ""))
            transient=http in {408,425,429,500,502,503,504} or any(x in msg.lower() for x in ("timeout","timed out","connection","temporarily","reset"))
            if result or not transient or attempt == 2: return result
            time.sleep(0.5 * (attempt + 1))
        return {}
    dhan._post = post
    dhan._retry_patch_installed = True
