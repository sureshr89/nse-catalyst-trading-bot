"""
STREAMLIT PAPER BOT RUNNER
==========================

Long-running PAPER trading worker for Streamlit.

IMPORTANT: main.py is imported lazily inside the worker. This keeps the
Streamlit dashboard able to open even if a trading dependency has an error.
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
PROJECT_ROOT = Path(__file__).resolve().parent
STATUS_FILE = PROJECT_ROOT / "outputs" / "bot_status.json"

_lock = threading.RLock()
_thread = None

_state = {
    "status": "STARTING",
    "message": "Paper bot is starting.",
    "last_cycle": None,
    "last_scan": None,
    "last_scan_completed": None,
    "scan_started_at": None,
    "scan_duration_seconds": None,
    "last_signal_count": 0,
    "last_scan_error": None,
    "scanner_status": "IDLE",
    "error": None,
    "worker_alive": False,
    "heartbeat": None,
    "cycle_count": 0,
    "scan_count": 0,
}


def _now():
    return datetime.now(INDIA_TZ)


def _iso_now():
    return _now().isoformat(timespec="seconds")


def _write_status(bot=None, **updates):
    global _state
    with _lock:
        _state.update(updates)
        _state["heartbeat"] = _iso_now()
        payload = dict(_state)
        payload["server_time_ist"] = _iso_now()
        payload["worker_alive"] = _thread is not None and _thread.is_alive()

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
                    bot.cooldown_until.isoformat() if bot.cooldown_until is not None else None
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
            self.cooldown_until = _now().replace(tzinfo=None) + timedelta(minutes=COOLDOWN_MINUTES)
        return result
    bot.monitor_position = MethodType(monitor_position_ist, bot)

    original_approve = bot.risk_engine.approve_trade
    def approve_trade_safe(self, signal):
        available = getattr(bot.paper_engine, "available_capital", TOTAL_CAPITAL)
        adjusted = _normalise_risk_quantity(signal, available)
        return original_approve(adjusted)
    bot.risk_engine.approve_trade = MethodType(approve_trade_safe, bot.risk_engine)

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
    bot.paper_engine.open_trade = MethodType(open_trade_safe, bot.paper_engine)


def _run_one_trading_day():
    # Lazy import: dashboard startup is independent from trading dependencies.
    from main import TradingBot

    bot = TradingBot()
    _patch_bot_for_ist(bot)
    _write_status(
        bot,
        status="RUNNING",
        message="Paper trading bot is running.",
        last_cycle=None,
        last_scan=None,
        last_scan_completed=None,
        scan_started_at=None,
        scan_duration_seconds=None,
        last_signal_count=0,
        last_scan_error=None,
        scanner_status="IDLE",
        error=None,
        cycle_count=0,
        scan_count=0,
    )

    original_scan = bot.scanner.scan
    def monitored_scan():
        started = time.monotonic()
        scan_started_at = _iso_now()
        _write_status(
            bot,
            scanner_status="SCANNING",
            last_scan=scan_started_at,
            scan_started_at=scan_started_at,
            last_scan_error=None,
            error=None,
            scan_count=int(_state.get("scan_count", 0)) + 1,
        )
        try:
            result = original_scan()
            signal_count = len(result) if isinstance(result, list) else 0
            _write_status(
                bot,
                last_signal_count=signal_count,
                message=f"Scanner completed. Final trade signals: {signal_count}.",
            )
            return result
        except Exception as error:
            _write_status(
                bot,
                last_scan_error=f"{type(error).__name__}: {error}",
                error=f"Scanner error: {type(error).__name__}: {error}",
            )
            raise
        finally:
            _write_status(
                bot,
                scanner_status="IDLE",
                last_scan_completed=_iso_now(),
                scan_duration_seconds=round(time.monotonic() - started, 2),
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
            cycle_count=int(_state.get("cycle_count", 0)) + 1,
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
    global _thread
    try:
        _write_status(status="STARTING", message="Paper bot worker started.", error=None, worker_alive=True)
        while True:
            try:
                now = _now()
                if now.weekday() >= 5:
                    _write_status(status="WAITING", message="Weekend. Waiting for the next Indian market session.", scanner_status="IDLE", last_scan=None, last_cycle=None, error=None)
                    time.sleep(30)
                    continue

                current = now.strftime("%H:%M")
                if current < TRADING_START:
                    _write_status(status="WAITING", message=f"Waiting for trading start at {TRADING_START} IST.", scanner_status="IDLE", last_scan=None, last_cycle=None, error=None)
                    time.sleep(15)
                    continue
                if current >= SQUARE_OFF_TIME:
                    _write_status(status="WAITING", message="Market session finished. Waiting for the next Indian market session.", scanner_status="IDLE", last_scan=None, last_cycle=None, error=None)
                    time.sleep(30)
                    continue

                _run_one_trading_day()
                time.sleep(5)
            except Exception as error:
                _write_status(status="ERROR", message="Trading worker hit an error and will retry.", scanner_status="ERROR", error=f"{type(error).__name__}: {error}")
                time.sleep(15)
    finally:
        with _lock:
            _state["worker_alive"] = False
        try:
            _write_status(status="STOPPED", message="Paper bot worker stopped.", worker_alive=False)
        except Exception:
            pass


def start_bot():
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run_bot, name="paper-trading-bot", daemon=True)
            _thread.start()
    return get_status()


def ensure_bot_running():
    with _lock:
        alive = _thread is not None and _thread.is_alive()
    if not alive:
        return start_bot()
    return get_status()


def get_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as file:
            disk_state = json.load(file)
    except Exception:
        disk_state = {}

    with _lock:
        current = dict(_state)
        alive = _thread is not None and _thread.is_alive()

    current.update(disk_state)
    current["worker_alive"] = alive
    if alive:
        if current.get("status") not in {"ERROR", "WAITING", "SCANNING"}:
            current["status"] = "RUNNING"
    else:
        if current.get("status") in {"RUNNING", "SCANNING", "STARTING"}:
            current["status"] = "STOPPED"
            current["message"] = "Paper bot worker is not running. Dashboard watchdog will restart it."
            current["error"] = current.get("error") or "Worker thread is not alive."
    return current
