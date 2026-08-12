"""
Durable paper-trading persistence.

Uses the local filesystem for fast operation and, when GITHUB_TOKEN is
available, mirrors the selected state files to this repository. Streamlit
Community Cloud exposes root-level secrets as environment variables, so the
worker can use GITHUB_TOKEN without storing credentials in source code.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests

REPO = os.getenv(
    "TRADING_BOT_GITHUB_REPOSITORY",
    "sureshr89/nse-catalyst-trading-bot",
)
BRANCH = os.getenv("TRADING_BOT_GITHUB_BRANCH", "main")
API_ROOT = f"https://api.github.com/repos/{REPO}/contents"

_lock = threading.RLock()
_last_sync: dict[str, float] = {}


def _token() -> str | None:
    value = os.getenv("GITHUB_TOKEN")
    if value:
        return value.strip()
    return None


def enabled() -> bool:
    return bool(_token())


def _headers() -> dict[str, str]:
    token = _token()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _local_path(path: str) -> Path:
    return Path(path)


def _remote_get(path: str):
    if not enabled():
        return None
    response = requests.get(
        f"{API_ROOT}/{path}",
        params={"ref": BRANCH},
        headers=_headers(),
        timeout=15,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _remote_read(path: str) -> str | None:
    item = _remote_get(path)
    if not item:
        return None
    encoded = item.get("content")
    if not encoded:
        return None
    return base64.b64decode(encoded.replace("\n", "")).decode("utf-8")


def sync_text(path: str, *, force: bool = False, min_interval: float = 60.0) -> bool:
    """Mirror one local text file to GitHub.

    Returns True when the remote file was updated. Sync failures never raise
    into the trading loop; local persistence remains the immediate fallback.
    """
    if not enabled():
        return False

    local = _local_path(path)
    if not local.exists():
        return False

    now = time.monotonic()
    with _lock:
        if not force and now - _last_sync.get(path, 0.0) < min_interval:
            return False
        try:
            content = local.read_text(encoding="utf-8")
            remote = _remote_get(path)
            payload = {
                "message": f"Persist trading data: {path}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": BRANCH,
            }
            if remote and remote.get("sha"):
                payload["sha"] = remote["sha"]
                response = requests.put(
                    f"{API_ROOT}/{path}",
                    headers=_headers(),
                    json=payload,
                    timeout=20,
                )
            else:
                response = requests.put(
                    f"{API_ROOT}/{path}",
                    headers=_headers(),
                    json=payload,
                    timeout=20,
                )
            response.raise_for_status()
            _last_sync[path] = now
            return True
        except Exception as error:
            print(f"Persistence sync warning for {path}: {type(error).__name__}: {error}")
            return False


def restore_text(path: str) -> bool:
    """Restore a remote file when the local file is missing or empty/header-only."""
    if not enabled():
        return False
    local = _local_path(path)
    try:
        local.parent.mkdir(parents=True, exist_ok=True)
        local_size = local.stat().st_size if local.exists() else 0
        if local_size > 0:
            return False
        content = _remote_read(path)
        if content is None:
            return False
        local.write_text(content, encoding="utf-8")
        return True
    except Exception as error:
        print(f"Persistence restore warning for {path}: {type(error).__name__}: {error}")
        return False


def save_json(path: str, payload: dict[str, Any]) -> bool:
    local = _local_path(path)
    local.parent.mkdir(parents=True, exist_ok=True)
    temporary = local.with_suffix(local.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        os.replace(temporary, local)
    except Exception as error:
        print(f"Persistence local-save warning for {path}: {type(error).__name__}: {error}")
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    sync_text(path, force=True)
    return True


def load_json(path: str) -> dict[str, Any] | None:
    local = _local_path(path)
    try:
        if not local.exists() or local.stat().st_size == 0:
            restore_text(path)
        if not local.exists() or local.stat().st_size == 0:
            return None
        return json.loads(local.read_text(encoding="utf-8"))
    except Exception as error:
        print(f"Persistence load warning for {path}: {type(error).__name__}: {error}")
        return None


def persist_engine_state(state: dict[str, Any]) -> None:
    save_json("outputs/paper_engine_state.json", state)


def load_engine_state() -> dict[str, Any] | None:
    return load_json("outputs/paper_engine_state.json")
