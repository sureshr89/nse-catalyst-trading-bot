"""
STREAMLIT PAPER BOT RUNNER
==========================

Long-running PAPER trading worker for Streamlit.

The worker waits outside the Indian market session, starts one TradingBot
for each trading day, and waits again after the 15:00 square-off. It never
calls Streamlit APIs directly.
"""

import json
import math
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
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK,
    TOTAL_CAPITAL,
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


def _normalise_risk_quantity(signal, available_capital):
    """
    Make the scanner quantity satisfy the configured risk band when a
    valid whole-number quantity exists.

    The scanner already sizes near MAX_RISK_PER_TRADE, but flooring can
    leave actual risk below MIN_REQUIRED_RISK. We therefore use the
    smallest quantity that reaches the minimum risk, provided it does not
    exceed the maximum-risk quantity or available capital.
    """
    if not isinstance(signal, dict):
        return signal

    try:
        entry = float(signal.get("entry"))
        stop_loss = float(signal.get("stop_loss"))
        risk_per_share = abs(entry - stop_loss)
    except (TypeError, ValueError):
        return signal

    if risk_per_share <= 0:
        return signal

    max_qty = math.floor(MAX_RISK_PER_TRADE / risk_per_share)
    min_qty = math.ceil(MIN_REQUIRED_RISK / risk_per_share)

    if max_qty <= 0 or min_qty > max_qty:
        return signal

    try:
        capital_qty = math.floor(float(available_capital) / entry)
    except (TypeError, ValueError, ZeroDivisionError):
        capital_qty = 0

    quantity = min_qty
    if quantity > capital_qty:
        return signal

    adjusted = dict(signal)
    adjusted["quantity"] = int(quantity)
    adjusted["risk_per_share"] = round(risk_per_share, 4)
    adjusted["actual_risk"] = round(risk_per_share * quantity, 2)
    adjusted["maximum_risk"] = round(MAX_RISK_PER_TRADE, 2)
    return adjusted


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

    # ------------------------------------------------------------
    # Risk sizing + rollback safety for the Streamlit worker.
    # RiskEngine currently registers an approved trade before the paper
    # engine opens it. If opening fails, undo that registration.
    # ------------------------------------------------------------
    original_approve = bot.risk_engine.approve_trade

    def approve_trade_safe(self, signal):
        available = getattr(
            bot.paper_engine,
            "available_capital",
            TOTAL_CAPITAL,
        )
        adjusted = _normalise_risk_quantity(
            signal,
            available,
        )
        return original_approve(adjusted)

    bot.risk_engine.approve_trade = MethodType(
        approve_trade_safe,
        bot.risk_engine,
    )

    original_open = bot.paper_engine.open_trade

    def open_trade_safe(self, trade):
        symbol = str(trade.get("symbol", "")).strip().upper()
        before_count = bot.risk_engine.get_trade_count(symbol)

        result = original_open(trade)

        if not result.get("opened", False):
            after_count = bot.risk_engine.get_trade_count(symbol)
            if after_count > before_count:
                bot.risk_engine.trade_counts[symbol] = before_count

        return result

    bot.paper_engine.open_trade = MethodType(
        open_trade_safe,
        bot.paper_engine,
    )


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
        # Timestamp is written immediately before the REAL scanner call.
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
        last_scan=None,
        last_cycle=None,
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
                    last_cycle=None,
                )
                time.sleep(30)
                continue

            current = now.strftime("%H:%M")

            # Before the configured trading start, keep the worker alive.
            if current < TRADING_START:
                _write_status(
                    status="WAITING",
                    message=f"Waiting for trading start at {TRADING_START} IST.",
                    scanner_status="IDLE",
                    last_scan=None,
                    last_cycle=None,
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
                    last_cycle=None,
                )
                time.sleep(30)
                continue

            _run_one_trading_day()
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
        if current.get("status") not in {"ERROR", "WAITING"}:
            current["status"] = "RUNNING"

    return current
