"""Compatibility wrapper for the retired duplicate Strategy 2 worker.

Strategy 2 is now owned exclusively by TradingBot in bot_runner.py. This
module intentionally does not create a second scanner/runtime/thread. Legacy
imports can safely call ensure_strategy2_running(), which delegates to the
single paper-bot owner.
"""
import json
from pathlib import Path

STATUS = Path("outputs/bot_status.json")
S2_DIAGNOSTICS = Path("outputs/strategy2_diagnostics.json")
S2_STATE = Path("outputs/strategy2_paper_engine_state.json")


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def ensure_strategy2_running():
    """Legacy entry point: start the one integrated paper-bot worker."""
    from bot_runner import ensure_bot_running
    return ensure_bot_running()


def get_strategy2_status():
    """Legacy read API backed by the integrated Strategy 2 state."""
    bot = _read(STATUS)
    diagnostics = _read(S2_DIAGNOSTICS)
    state = _read(S2_STATE)
    return {
        "status": bot.get("status", "STARTING"),
        "message": "Strategy 2 is integrated into the single NIFTY 500 paper-bot worker.",
        "worker_alive": bool(bot.get("worker_alive", False)),
        "last_scan": diagnostics.get("timestamp"),
        "last_signal_count": int(diagnostics.get("signals", 0) or 0),
        "available_capital": float(state.get("available_capital", 250000) or 250000),
        "open_positions": len(state.get("open_positions", {}) or {}),
        "daily_pnl": float(diagnostics.get("daily_pnl", 0) or 0),
        "last_error": bot.get("last_scan_error") or bot.get("error"),
    }
