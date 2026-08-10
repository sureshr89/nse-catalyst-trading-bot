"""
STREAMLIT PAPER BOT RUNNER
==========================

Long-running PAPER trading worker for Streamlit.

The worker waits outside the Indian market session, starts one TradingBot
for each trading day, and waits again after the 15:00 square-off. It never
calls Streamlit APIs directly.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import MethodType
from zoneinfo import ZoneInfo

from main import TradingBot
from config.settings import (
    COOLDOWN_MINUTES,
    TRADING_START,
    SQUARE_OFF_TIME,
)


INDIA_TZ = ZoneInfo("Asia/Kolkata")
STATUS_FILE = Path("outputs/bot_status.json")

_lock = threading.Lock()
_thread = None
_state = {
    "status": "WAITING",
    "message": "Waiting for the Indian market session.",
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

    now = _now().replace(tzinfo=None)

    if now >= self.cooldown_until:
        self.cooldown_until = None
        return False

    return True


def _patch_bot_for_ist(bot):
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

    bot.monitor_position = MethodType(monitor_position_ist, bot)


def _run_one_trading_day():
    """Run one TradingBot instance for the current trading day."""

    bot = TradingBot()
    _patch_bot_for_ist(bot)

    # Clear stale timestamps from a previous day/session.
    _write_status(
        bot,
        status="RUNNING",
        message="Paper trading bot is running.",
        last_cycle=None,
        last_scan=None,
        scanner_status="IDLE",
        error=None,
    )

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
            _write_status(bot, scanner_status="IDLE")

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
        status="WAITING",
        message="Trading day complete. Waiting for the next Indian market session.",
        scanner_status="IDLE",
    )


def _run_bot():
    while True:
        try:
            now = _now()

            # Saturday/Sunday: no market session.
            if now.weekday() >= 5:
                _write_status(
                    status="WAITING",
                    message="Weekend. Waiting for the next Indian market session.",
                    scanner_status="IDLE",
                    last_scan=None,
                )
                time.sleep(30)
                continue

            current = now.strftime("%H:%M")

            # Before the configured trading start, keep the worker alive so
            # it can automatically begin scanning when the session opens.
            if current < TRADING_START:
                _write_status(
                    status="WAITING",
                    message=f"Waiting for trading start at {TRADING_START} IST.",
                    scanner_status="IDLE",
                    last_scan=None,
                )
                time.sleep(15)
                continue

            # After square-off, wait for the next day instead of repeatedly
            # restarting TradingBot on every Streamlit refresh.
            if current >= SQUARE_OFF_TIME:
                _write_status(
                    status="WAITING",
                    message="Market session finished. Waiting for the next Indian market session.",
                    scanner_status="IDLE",
                    last_scan=None,
                )
                time.sleep(30)
                continue

            _run_one_trading_day()

            # Avoid immediately creating another bot after a normal 15:00
            # completion.
            time.sleep(30)

        except Exception as error:
            _write_status(
                status="ERROR",
                message="Trading bot stopped because of an error.",
                scanner_status="ERROR",
                error=f"{type(error).__name__}: {error}",
            )
            time.sleep(30)


def start_bot():
    """Start exactly one long-running paper bot worker."""
    global _thread

    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(
                target=_run_bot,
                name="paper-trading-bot",
                daemon=True,
            )
            _thread.start()

    return get_status()


def get_status():
    """Read the latest runtime status."""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
            disk_state = json.load(file)
    except Exception:
        disk_state = {}

    with _lock:
        current = dict(_state)

    current.update(disk_state)

    if _thread is not None and _thread.is_alive():
        # Preserve WAITING/ERROR state from the worker; RUNNING means an
        # actual TradingBot session is active.
        if current.get("status") not in {"ERROR", "WAITING"}:
            current["status"] = "RUNNING"

    return current
