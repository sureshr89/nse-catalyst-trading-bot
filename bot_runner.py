"""
STREAMLIT PAPER BOT RUNNER
==========================

Starts exactly one paper-trading TradingBot in a background thread for the
Streamlit process. The worker never calls Streamlit APIs. It writes a small
runtime status file so the dashboard can show the bot's real state.

This is PAPER TRADING ONLY. LIVE_TRADING must remain False.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from types import MethodType
from zoneinfo import ZoneInfo

from main import TradingBot
from config.settings import COOLDOWN_MINUTES


INDIA_TZ = ZoneInfo("Asia/Kolkata")
STATUS_FILE = Path("outputs/bot_status.json")

_lock = threading.Lock()
_thread = None
_finished = False
_state = {
    "status": "STOPPED",
    "message": "Bot has not been started.",
    "last_cycle": None,
    "last_scan": None,
    "scanner_status": "IDLE",
    "error": None,
}


def _now():
    return datetime.now(INDIA_TZ)


def _iso_now():
    return _now().isoformat(timespec="seconds")


def _write_status(bot=None, **updates):
    global _state

    with _lock:
        _state.update(updates)

        payload = dict(_state)
        payload["server_time_ist"] = _iso_now()

        if bot is not None:
            try:
                session = bot.paper_engine.summary()
                payload["open_positions"] = session.get("open_positions", 0)
                payload["available_capital"] = session.get("available_capital", 0.0)
                payload["used_capital"] = session.get("used_capital", 0.0)
                payload["session_pnl"] = session.get("total_pnl", 0.0)
            except Exception:
                pass

            try:
                journal = bot.journal.summary()
                payload["total_trades"] = journal.get("total_trades", 0)
                payload["winning_trades"] = journal.get("winning_trades", 0)
                payload["losing_trades"] = journal.get("losing_trades", 0)
                payload["journal_pnl"] = journal.get("total_pnl", 0.0)
            except Exception:
                pass

            try:
                payload["daily_pnl"] = bot.daily_pnl
                payload["cooldown_until"] = (
                    bot.cooldown_until.isoformat()
                    if bot.cooldown_until is not None
                    else None
                )
            except Exception:
                pass

        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATUS_FILE.with_suffix(".tmp")

        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, default=str)

        os.replace(temporary, STATUS_FILE)


def _ist_current_time(self):
    return _now().strftime("%H:%M")


def _ist_cooldown_active(self):
    if self.cooldown_until is None:
        return False

    # main.py stores cooldown_until as a naive datetime. Compare it with
    # the current IST time made naive so there is no aware/naive mismatch.
    now = _now().replace(tzinfo=None)

    if now >= self.cooldown_until:
        self.cooldown_until = None
        return False

    return True


def _patch_bot_for_ist(bot):
    """Keep the existing strategy but make bot clock decisions use IST."""

    bot.current_time = MethodType(_ist_current_time, bot)
    bot.cooldown_active = MethodType(_ist_cooldown_active, bot)

    original_monitor = bot.monitor_position

    def monitor_position_ist(self, symbol):
        before = self.cooldown_until
        result = original_monitor(symbol)

        if self.cooldown_until is not None and self.cooldown_until != before:
            self.cooldown_until = (
                _now().replace(tzinfo=None)
                + timedelta(minutes=COOLDOWN_MINUTES)
            )

        return result

    bot.monitor_position = MethodType(
        monitor_position_ist,
        bot,
    )


def _run_bot():
    global _state, _finished

    bot = None

    try:
        bot = TradingBot()
        _patch_bot_for_ist(bot)

        _write_status(
            bot,
            status="RUNNING",
            message="Paper trading bot is running.",
            error=None,
            scanner_status="IDLE",
        )

        # Record a scanner run only when ScannerEngine.scan() is actually
        # called. This prevents false scanner timestamps outside the entry
        # window.
        original_scan = bot.scanner.scan

        def monitored_scan():
            _write_status(
                bot,
                scanner_status="SCANNING",
                last_scan=_iso_now(),
                error=None,
            )

            try:
                return original_scan()
            finally:
                _write_status(
                    bot,
                    scanner_status="IDLE",
                )

        bot.scanner.scan = monitored_scan

        original_cycle = bot.run_cycle

        def monitored_cycle():
            _write_status(
                bot,
                status="RUNNING",
                message="Paper trading bot is running.",
                last_cycle=_iso_now(),
                error=None,
            )

            return original_cycle()

        bot.run_cycle = monitored_cycle
        bot.run()

        _write_status(
            bot,
            status="STOPPED",
            message="Trading day complete. Bot will not restart until the Streamlit app is restarted.",
            scanner_status="IDLE",
        )

        with _lock:
            _finished = True

    except Exception as error:
        _write_status(
            bot,
            status="ERROR",
            message="Trading bot stopped because of an error.",
            scanner_status="ERROR",
            error=f"{type(error).__name__}: {error}",
        )

        with _lock:
            _finished = True


def start_bot():
    """Start the paper bot once for the current Streamlit process."""

    global _thread

    with _lock:
        # Already running.
        if _thread is not None and _thread.is_alive():
            return get_status()

        # The trading day has already completed. Do not restart the bot on
        # every Streamlit rerun after 15:00.
        if _finished:
            return get_status()

        _thread = threading.Thread(
            target=_run_bot,
            name="paper-trading-bot",
            daemon=True,
        )
        _thread.start()

    return get_status()


def get_status():
    """Read the latest runtime status without touching the bot thread."""

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
            disk_state = json.load(file)
    except Exception:
        disk_state = dict(_state)

    with _lock:
        current = dict(_state)

    current.update(disk_state)

    if _thread is not None and _thread.is_alive():
        current["status"] = "RUNNING"

    return current
