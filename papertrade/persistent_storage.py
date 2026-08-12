"""Small persistence bridge for Streamlit's ephemeral filesystem.

When GITHUB_TOKEN is configured in the deployment environment, selected local
CSV files are restored from and synchronized back to the bot repository.
Without the token the bot keeps its existing local-file behavior unchanged.
"""

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


REPO = os.getenv("GITHUB_REPOSITORY", "sureshr89/nse-catalyst-trading-bot")
BRANCH = os.getenv("GITHUB_BRANCH", "main")
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
API_ROOT = f"https://api.github.com/repos/{REPO}/contents"


def enabled():
    return bool(TOKEN)


def _request(url, method="GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nse-catalyst-trading-bot",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def restore(local_path, repo_path):
    """Restore a tracked file from GitHub if persistence is configured."""
    if not enabled():
        return False
    try:
        info = _request(f"{API_ROOT}/{repo_path}?ref={BRANCH}")
        encoded = info.get("content", "").replace("\n", "")
        if not encoded:
            return False
        content = base64.b64decode(encoded).decode("utf-8")
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
    except Exception as error:
        print(f"Persistent restore skipped for {repo_path}: {error}")
        return False


def sync(local_path, repo_path, message):
    """Push the current local file to GitHub when persistence is configured."""
    if not enabled():
        return False
    path = Path(local_path)
    if not path.exists():
        return False
    try:
        content = path.read_bytes()
        encoded = base64.b64encode(content).decode("ascii")
        url = f"{API_ROOT}/{repo_path}"
        try:
            current = _request(f"{url}?ref={BRANCH}")
            sha = current.get("sha")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                sha = None
            else:
                raise
        payload = {
            "message": message,
            "content": encoded,
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
        _request(url, method="PUT", payload=payload)
        return True
    except Exception as error:
        print(f"Persistent sync skipped for {repo_path}: {error}")
        return False
