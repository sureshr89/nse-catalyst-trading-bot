"""Reliable paper-trading worker launcher for Streamlit Cloud.

The bot worker already has process-safe file locking and a daemon thread in
bot_runner.py. Streamlit reruns the page, but the Python process remains alive,
so starting that existing worker thread is more reliable than spawning a second
Python interpreter from Streamlit Cloud.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bot_runner import STATUS_FILE, OUTPUT_DIR, ensure_bot_running, get_status

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _heartbeat_fresh(status, max_age=90):
    try:
        stamp = datetime.fromisoformat(str(status.get("heartbeat", "")).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=INDIA_TZ)
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max_age
    except Exception:
        return False


def _read_status():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_worker_process():
    """Ensure the existing singleton bot worker is running and return its status."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        status = ensure_bot_running()
        if not isinstance(status, dict):
            status = get_status()
    except Exception as error:
        status = _read_status()
        status["worker_alive"] = False
        status["status"] = "ERROR"
        status["error"] = f"Worker launcher: {type(error).__name__}: {error}"
        return status

    # Read the persisted heartbeat after starting/checking the worker so the
    # dashboard sees the same state written by bot_runner.
    disk_status = _read_status()
    if disk_status:
        status.update(disk_status)
    status["worker_alive"] = bool(status.get("worker_alive")) and _heartbeat_fresh(status)
    return status


if __name__ == "__main__":
    print(json.dumps(ensure_worker_process(), indent=2, default=str))
