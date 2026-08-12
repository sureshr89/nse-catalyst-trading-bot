"""
STREAMLIT PAPER BOT RUNNER
==========================

Long-running PAPER trading worker for Streamlit.

The worker is protected by a process/file lock so Streamlit reruns or
multiple module instances cannot start competing paper-bot workers.
Status writes use a unique temporary file plus an OS-level file lock before
os.replace(), preventing bot_status.tmp collisions.
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

try:
    import fcntl
except ImportError:  # pragma: no cover - Streamlit deployment is normally Linux
    fcntl = None

from config.settings import (
    COOLDOWN_MINUTES,
    TRADING_START,
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK,
    TOTAL_CAPITAL,
    SCAN_INTERVAL_SECONDS,
)

INDIA_TZ = ZoneInfo("Asia/Kolkata")
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
STATUS_FILE = OUTPUT_DIR / "bot_status.json"
STATUS_LOCK_FILE = OUTPUT_DIR / "bot_status.lock"
WORKER_LOCK_FILE = OUTPUT_DIR / "paper_bot.worker.lock"

_lock = threading.RLock()
_thread = None
_worker_lock_handle = None

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
    "worker_id": None,
    "trading_start": TRADING_START,
    "last_entry_time": LAST_ENTRY_TIME,
    "square_off_time": SQUARE_OFF_TIME,
    "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
}


def _now():
    return datetime.now(INDIA_TZ)


def _iso_now():
    return _now().isoformat(timespec="seconds")


def _worker_id():
    return f"pid-{os.getpid()}-thread-{threading.get_ident()}"


def _with_file_lock(lock_path):
    """Return an opened lock file held by the caller until it is closed."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    if fcntl is not None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
    return handle


def _release_file_lock(handle):
    if handle is None:
        return
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def _write_status(bot=None, **updates):
    """Update in-memory status and atomically publish it to disk.

    Each writer gets its own temporary filename. The status lock prevents
    concurrent writers from replacing the same target while another writer is
    in the middle of publishing its state.
    """
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

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        status_lock = _with_file_lock(STATUS_LOCK_FILE)
        if status_lock is None:
            # Do not turn a diagnostic/status collision into a trading-worker
            # crash. The in-memory state remains valid and the next heartbeat
            # will publish it.
            return
        temporary = OUTPUT_DIR / (
            f"bot_status.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
        )
        try:
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, default=str)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, STATUS_FILE)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        finally:
            _release_file_lock(status_lock)


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

    original_force_square_off = bot.force_square_off

    def force_square_off_ist(self):
        symbols = list(self.paper_engine.open_positions.keys())
        if not symbols:
            return

        print()
        print("=" * 100)
        print("MANDATORY 15:00 SQUARE-OFF")
        print("=" * 100)

        exit_time = _now()

        for symbol in symbols:
            candle = None
            try:
                candle = self.price_data.latest_candle(symbol, "1m")
            except Exception as error:
                print(symbol, "1-minute square-off data error:", error)

            if candle is None:
                try:
                    candle = self.price_data.latest_candle(symbol, "5m")
                except Exception as error:
                    print(symbol, "5-minute square-off data error:", error)

            if candle is None:
                print(symbol, ": no market price available for mandatory square-off.")
                continue

            try:
                exit_price = float(candle.get("Close"))
            except (TypeError, ValueError):
                print(symbol, ": invalid square-off close price.")
                continue

            closed_trade = self.paper_engine.close_position(
                symbol,
                exit_price,
                exit_time,
                "SQUARE_OFF"
            )

            if closed_trade is None:
                continue

            pnl = float(closed_trade.get("pnl", 0) or 0)
            self.daily_pnl += pnl
            self.journal.log_trade(closed_trade)

            print(
                symbol,
                "SQUARE_OFF",
                "Exit:",
                closed_trade.get("exit_price"),
                "P&L:",
                pnl
            )

        print("=" * 100)

    bot.force_square_off = MethodType(force_square_off_ist, bot)


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
        worker_id=_worker_id(),
        trading_start=TRADING_START,
        last_entry_time=LAST_ENTRY_TIME,
        square_off_time=SQUARE_OFF_TIME,
        scan_interval_seconds=SCAN_INTERVAL_SECONDS,
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
    global _thread, _worker_lock_handle
    try:
        _write_status(
            status="STARTING",
            message="Paper bot worker started.",
            error=None,
            worker_alive=True,
            worker_id=_worker_id(),
            trading_start=TRADING_START,
            last_entry_time=LAST_ENTRY_TIME,
            square_off_time=SQUARE_OFF_TIME,
            scan_interval_seconds=SCAN_INTERVAL_SECONDS,
        )
        while True:
            try:
                now = _now()
                if now.weekday() >= 5:
                    _write_status(
                        status="WAITING",
                        message="Weekend. Waiting for the next Indian market session.",
                        scanner_status="IDLE",
                        last_scan=None,
                        last_cycle=None,
                        error=None,
                    )
                    time.sleep(30)
                    continue

                current = now.strftime("%H:%M")
                if current < TRADING_START:
                    _write_status(
                        status="WAITING",
                        message=f"Waiting for trading start at {TRADING_START} IST.",
                        scanner_status="IDLE",
                        last_scan=None,
                        last_cycle=None,
                        error=None,
                    )
                    time.sleep(15)
                    continue
                if current >= SQUARE_OFF_TIME:
                    _write_status(
                        status="WAITING",
                        message="Market session finished. Waiting for the next Indian market session.",
                        scanner_status="IDLE",
                        last_scan=None,
                        last_cycle=None,
                        error=None,
                    )
                    time.sleep(30)
                    continue

                _run_one_trading_day()
                time.sleep(5)
            except Exception as error:
                # Never let the error-reporting path kill the worker. _write_status
                # itself is designed to survive status-file contention.
                try:
                    _write_status(
                        status="ERROR",
                        message="Trading worker hit an error and will retry.",
                        scanner_status="ERROR",
                        error=f"{type(error).__name__}: {error}",
                    )
                except Exception:
                    pass
                time.sleep(15)
    finally:
        with _lock:
            _state["worker_alive"] = False
            _state["status"] = "STOPPED"
        try:
            _write_status(
                status="STOPPED",
                message="Paper bot worker stopped.",
                worker_alive=False,
            )
        except Exception:
            pass
        _release_file_lock(_worker_lock_handle)
        _worker_lock_handle = None
        _thread = None


def start_bot():
    global _thread, _worker_lock_handle
    with _lock:
        if _thread is not None and _thread.is_alive():
            return get_status()

        # A file lock makes the worker single-instance across Streamlit module
        # instances and, when applicable, across multiple server processes.
        lock_handle = _with_file_lock(WORKER_LOCK_FILE)
        if lock_handle is None:
            _state["status"] = "WAITING"
            _state["message"] = "Another paper-bot worker already owns the worker lock."
            _state["worker_alive"] = False
            _state["error"] = None
            return get_status()

        _worker_lock_handle = lock_handle
        _thread = threading.Thread(
            target=_run_bot,
            name="paper-trading-bot",
            daemon=True,
        )
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
