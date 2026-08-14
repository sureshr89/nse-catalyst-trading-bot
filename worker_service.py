"""Independent paper-trading worker launcher for Streamlit Cloud.

Streamlit reruns page scripts frequently, so the trading loop must not depend on a
Streamlit script-thread lifetime. This module runs the existing bot worker in a
separate Python process and uses the existing file lock/status file for singleton
coordination.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bot_runner import WORKER_LOCK_FILE, STATUS_FILE, OUTPUT_DIR

INDIA_TZ = ZoneInfo("Asia/Kolkata")
PID_FILE = OUTPUT_DIR / "paper_bot.pid"


def _heartbeat_fresh(status, max_age=90):
    try:
        stamp = datetime.fromisoformat(str(status.get("heartbeat", "")).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        return 0 <= (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() <= max_age
    except Exception:
        return False


def _read_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _pid_alive():
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def ensure_worker_process():
    """Return status and start one independent worker without a launch race."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    status = _read_status()
    pid = _pid_alive()
    if pid and _heartbeat_fresh(status):
        status["worker_alive"] = True
        status["worker_pid"] = pid
        return status

    lock_handle = None
    try:
        lock_handle = open(WORKER_LOCK_FILE, "a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, BlockingIOError):
            lock_handle.close()
            status = _read_status()
            status["worker_alive"] = _heartbeat_fresh(status)
            return status

        # Keep the probe lock until the child has acquired the real worker lock.
        # This prevents two Streamlit processes from launching duplicate workers.
        log_path = OUTPUT_DIR / "paper_bot_worker.log"
        log = open(log_path, "a", encoding="utf-8")
        child = None
        try:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                cwd=str(Path(__file__).resolve().parent),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
                close_fds=True,
            )
            PID_FILE.write_text(str(child.pid), encoding="utf-8")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                time.sleep(0.1)
                child_status = _read_status()
                child_pid = _pid_alive()
                if child_pid == child.pid and _heartbeat_fresh(child_status, max_age=10):
                    child_status["worker_alive"] = True
                    child_status["worker_pid"] = child.pid
                    return child_status
                if child.poll() is not None:
                    break
            status = _read_status()
            status["worker_alive"] = bool(_pid_alive())
            status["worker_pid"] = child.pid
            return status
        finally:
            try:
                log.close()
            except Exception:
                pass
            try:
                import fcntl
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            lock_handle.close()
    except Exception as error:
        try:
            if lock_handle:
                lock_handle.close()
        except Exception:
            pass
        status = _read_status()
        status["worker_alive"] = _heartbeat_fresh(status)
        status["error"] = f"Worker launcher: {type(error).__name__}: {error}"
        return status


def run_worker():
    """Child-process entry point; keep the worker lock for its full lifetime."""
    from bot_runner import _run_bot, _with_file_lock
    import bot_runner
    lock = _with_file_lock(WORKER_LOCK_FILE)
    if lock is None:
        return 0
    bot_runner._worker_lock_handle = lock
    bot_runner._thread = __import__("threading").current_thread()
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        _run_bot()
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    if "--worker" in sys.argv:
        raise SystemExit(run_worker())
    print(json.dumps(ensure_worker_process(), indent=2, default=str))
