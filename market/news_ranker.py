"""Non-blocking Google News RSS ranker for sector-filtered NIFTY 500 stocks.

News is a ranking input only. It never upgrades an otherwise invalid market
snapshot into a tradeable state. Positive news is preferred for BUY candidates,
negative news for SELL candidates, while neutral/no-news candidates remain
eligible so news availability cannot silently become a hard gate.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import RLock
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import re
import xml.etree.ElementTree as ET
from config.settings import NEWS_CACHE_SECONDS, NEWS_MAX_BATCH_SYMBOLS, NEWS_MAX_BATCHES_PER_REFRESH

_POSITIVE = {
    "order win": 5, "large order": 5, "contract win": 5, "major order": 5,
    "profit rises": 4, "profit jumps": 4, "profit surges": 4, "profit climbs": 4,
    "revenue rises": 3, "revenue jumps": 3, "sales rise": 3, "strong results": 4,
    "beats estimates": 5, "beats expectations": 5, "upgrade": 3, "buy rating": 3,
    "target raised": 3, "dividend": 2, "capacity expansion": 3, "approval": 2,
    "wins": 2, "growth": 2, "record profit": 5, "record revenue": 5,
}
_NEGATIVE = {
    "fraud": -6, "scam": -6, "default": -6, "downgrade": -3, "sell rating": -3,
    "target cut": -3, "profit falls": -4, "profit drops": -4, "profit declines": -4,
    "revenue falls": -3, "revenue drops": -3, "loss widens": -5, "weak results": -4,
    "misses estimates": -5, "misses expectations": -5, "penalty": -3, "fine": -3,
    "investigation": -4, "probe": -4, "regulatory action": -4, "debt default": -6,
    "layoffs": -2, "warning": -2, "recall": -3,
}

_CACHE = {}
_LOCK = RLock()
_INFLIGHT = set()
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="news")
_REFRESH_CURSOR = 0


def _now():
    return datetime.now(timezone.utc)


def _age_seconds(value):
    try:
        return max(0.0, (_now() - value).total_seconds())
    except Exception:
        return 10**9


def _score_title(text):
    low = str(text).lower()
    score = 0
    for phrase, weight in _POSITIVE.items():
        if phrase in low:
            score += weight
    for phrase, weight in _NEGATIVE.items():
        if phrase in low:
            score += weight
    return score


def _fetch_batch(symbols):
    terms = " OR ".join(f'"{s}"' for s in symbols)
    url = "https://news.google.com/rss/search?q=" + quote_plus(terms + " NSE stock") + "&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 NSE-Catalyst/1.0"})
        with urlopen(req, timeout=2.0) as response:
            root = ET.fromstring(response.read())
    except Exception:
        return {}

    out = {s: [] for s in symbols}
    for item in root.findall("./channel/item")[:40]:
        title = (item.findtext("title") or "").strip()
        summary = re.sub(r"<[^>]+>", " ", item.findtext("description") or "").strip()
        source = (item.findtext("source") or "").strip()
        text = f"{title} {summary}"
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except Exception:
            published = _now()
        score = _score_title(text)
        if score == 0:
            continue
        for symbol in symbols:
            # Require an exact word-like symbol match to reduce accidental matches
            # (e.g. a ticker embedded inside another company name).
            if re.search(rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])", text, flags=re.I):
                out[symbol].append({"title": title, "score": score, "published": published.isoformat(), "source": source})
    return out


def _store_batch(result):
    with _LOCK:
        touched = set()
        for symbol, headlines in (result or {}).items():
            touched.add(symbol)
            if not headlines:
                continue
            total = sum(int(h.get("score", 0)) for h in headlines)
            latest = max(headlines, key=lambda h: str(h.get("published", "")))
            try:
                age = max(0.0, (_now() - datetime.fromisoformat(latest["published"])).total_seconds())
            except Exception:
                age = 10**9
            recency = max(0.0, 1.0 - age / 21600.0)
            strength = max(-100.0, min(100.0, total * 8.0 * (0.5 + 0.5 * recency)))
            _CACHE[symbol] = {"score": strength, "headlines": headlines, "updated_at": _now()}
        _INFLIGHT.difference_update(touched)


def _safe_store(future):
    try:
        _store_batch(future.result())
    except Exception:
        # Only release symbols represented by the future where possible. Since
        # the executor callback has no batch metadata, clearing the in-flight
        # set is safer than leaving a permanent deadlock in refresh_async.
        with _LOCK:
            _INFLIGHT.clear()


def refresh_async(symbols):
    global _REFRESH_CURSOR
    symbols = [str(s).upper().strip() for s in symbols if str(s).strip()]
    if not symbols:
        return
    with _LOCK:
        stale = [s for s in dict.fromkeys(symbols) if s not in _CACHE or _age_seconds(_CACHE[s]["updated_at"]) >= NEWS_CACHE_SECONDS]
        if not stale:
            return
        start = _REFRESH_CURSOR % len(stale)
        ordered = stale[start:] + stale[:start]
        _REFRESH_CURSOR += NEWS_MAX_BATCHES_PER_REFRESH * NEWS_MAX_BATCH_SYMBOLS
        batches = [ordered[i:i + NEWS_MAX_BATCH_SYMBOLS] for i in range(0, len(ordered), NEWS_MAX_BATCH_SYMBOLS)][:NEWS_MAX_BATCHES_PER_REFRESH]
        for batch in batches:
            if any(s in _INFLIGHT for s in batch):
                continue
            _INFLIGHT.update(batch)
            future = _EXECUTOR.submit(_fetch_batch, batch)
            future.add_done_callback(_safe_store)


def rank(symbols, side):
    """Rank candidates by matching news sentiment without excluding no-news stocks."""
    side = str(side).upper()
    rows = []
    with _LOCK:
        for symbol in dict.fromkeys(symbols):
            key = str(symbol).upper().strip()
            item = _CACHE.get(key)
            score = float(item["score"]) if item and _age_seconds(item["updated_at"]) < NEWS_CACHE_SECONDS else 0.0
            if side == "BUY":
                priority = 0 if score > 0 else 1
            elif side == "SELL":
                priority = 0 if score < 0 else 1
            else:
                priority = 1
            rows.append((key, score, priority))
    rows.sort(key=lambda x: (x[2], -abs(x[1]), x[0]))
    return [(symbol, score) for symbol, score, _ in rows]


def snapshot():
    with _LOCK:
        return {k: {"score": v["score"], "headlines": list(v["headlines"])} for k, v in _CACHE.items()}
