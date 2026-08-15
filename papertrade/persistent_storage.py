"""Persistence bridge for Streamlit's ephemeral filesystem.

Runtime data can be persisted to a dedicated Git branch, but public repositories
are blocked by default because trading history should not become public data.
For a durable private setup, use a private repository or a private external store
such as Google Drive/database.
"""
import base64,json,os,time,urllib.error,urllib.request
from pathlib import Path
REPO=os.getenv("GITHUB_REPOSITORY","sureshr89/nse-catalyst-trading-bot");BRANCH=os.getenv("GITHUB_DATA_BRANCH","data");TOKEN=os.getenv("GITHUB_TOKEN","").strip();ALLOW_PUBLIC_DATA=os.getenv("GITHUB_ALLOW_PUBLIC_DATA","false").strip().lower()=="true";API_ROOT=f"https://api.github.com/repos/{REPO}/contents";_REPO_PRIVATE=None;_LAST_SIGNAL_SYNC=0.0;_MAX_SYNC_RETRIES=3

def _repo_is_private():
 global _REPO_PRIVATE
 if _REPO_PRIVATE is not None:return _REPO_PRIVATE
 try:
  request=urllib.request.Request(f"https://api.github.com/repos/{REPO}",headers={"Accept":"application/vnd.github+json","User-Agent":"nse-catalyst-trading-bot"})
  with urllib.request.urlopen(request,timeout=10) as response:_REPO_PRIVATE=bool(json.loads(response.read().decode("utf-8")).get("private",False))
 except Exception:_REPO_PRIVATE=False
 return _REPO_PRIVATE

def enabled():return bool(TOKEN) and (_repo_is_private() or ALLOW_PUBLIC_DATA)

def _request(url,method="GET",payload=None):
 headers={"Accept":"application/vnd.github+json","User-Agent":"nse-catalyst-trading-bot","X-GitHub-Api-Version":"2026-03-10"}
 if TOKEN:headers["Authorization"]=f"Bearer {TOKEN}"
 data=None
 if payload is not None:data=json.dumps(payload).encode("utf-8");headers["Content-Type"]="application/json"
 request=urllib.request.Request(url,data=data,headers=headers,method=method)
 with urllib.request.urlopen(request,timeout=15) as response:
  raw=response.read().decode("utf-8");return json.loads(raw) if raw else {}

def restore(local_path,repo_path):
 if not enabled():return False
 try:
  info=_request(f"{API_ROOT}/{repo_path}?ref={BRANCH}");encoded=info.get("content","").replace("\n","")
  if not encoded:return False
  content=base64.b64decode(encoded).decode("utf-8");path=Path(local_path);path.parent.mkdir(parents=True,exist_ok=True)
  # Never overwrite non-empty runtime data during automatic startup restore.
  # This prevents a stale remote snapshot from rolling back newer local state.
  if path.exists() and path.stat().st_size>0 and os.getenv("GITHUB_FORCE_RESTORE","false").strip().lower()!="true":return False
  path.write_text(content,encoding="utf-8");return True
 except Exception as error:print(f"Persistent restore skipped for {repo_path}: {error}");return False

def _current_sha(url):
 try:return _request(f"{url}?ref={BRANCH}").get("sha")
 except urllib.error.HTTPError as error:
  if error.code==404:return None
  raise

def sync(local_path,repo_path,message):
 global _LAST_SIGNAL_SYNC
 if not enabled():return False
 if "scanner signal" in str(message).lower():
  now=time.monotonic()
  if now-_LAST_SIGNAL_SYNC<60.0:return False
  _LAST_SIGNAL_SYNC=now
 path=Path(local_path)
 if not path.exists():return False
 try:
  for attempt in range(_MAX_SYNC_RETRIES):
   encoded=base64.b64encode(path.read_bytes()).decode("ascii");url=f"{API_ROOT}/{repo_path}";sha=_current_sha(url);payload={"message":message,"content":encoded,"branch":BRANCH}
   if sha:payload["sha"]=sha
   try:_request(url,method="PUT",payload=payload);return True
   except urllib.error.HTTPError as error:
    if error.code==409 and attempt<_MAX_SYNC_RETRIES-1:time.sleep(0.25*(attempt+1));continue
    raise
  return False
 except Exception as error:print(f"Persistent sync skipped for {repo_path}: {error}");return False

def restore_json(local_path,repo_path):return restore(local_path,repo_path)
def sync_json(local_path,repo_path,message):return sync(local_path,repo_path,message)
