"""Runtime resilience patch for the NSE Catalyst paper-trading engine.

This module intentionally leaves the Streamlit dashboard and S1-S5 rules unchanged.
It prevents transient market-data/API failures from killing the persistent worker,
while preserving the exact error in diagnostics for inspection.
"""
from __future__ import annotations

import time


def install(MasterEngine):
    if getattr(MasterEngine, "_stability_patch_installed", False):
        return MasterEngine

    original_run_cycle = MasterEngine.run_cycle

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
                    if callable(writer):
                        writer()
            except Exception:
                pass
            return []

    MasterEngine.run_cycle = run_cycle
    MasterEngine._stability_patch_installed = True
    return MasterEngine


def install_dhan_retry():
    """Add bounded retries around transient Dhan HTTP/network failures."""
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
            status = dhan.dhan_status()
            http = status.get("http_status")
            msg = str(status.get("message", ""))
            transient = http in {408, 425, 429, 500, 502, 503, 504} or any(
                x in msg.lower()
                for x in ("timeout", "timed out", "connection", "temporarily", "reset")
            )
            if result or not transient or attempt == 2:
                return result
            time.sleep(0.75 * (attempt + 1))
        return {}

    dhan._post = post
    dhan._retry_patch_installed = True
