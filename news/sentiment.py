"""Deterministic, paper-trading-safe Yahoo Finance headline sentiment.

This module deliberately does not use an LLM or paid API. It uses the local
CSV dictionary plus context-aware phrase precedence. Ambiguous headlines are
NEUTRAL and therefore cannot pass the final news gate.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import yfinance as yf

CSV_PATH = Path("data/news_sentiment_keywords.csv")
POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"
NEUTRAL = "NEUTRAL"

_NEGATIVE_MODIFIERS = {"weak", "poor", "lower", "decline", "declining", "slow", "slower", "slowing", "disappointing", "miss", "misses", "below", "cuts", "cut", "falls", "fall", "drops", "drop"}
_POSITIVE_MODIFIERS = {"strong", "robust", "higher", "accelerating", "record", "beats", "beat", "above", "raises", "raised", "improves", "improved", "wins", "won"}


def _load_rules() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return sorted(rows, key=lambda r: len(str(r.get("keyword", ""))), reverse=True)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%₹.$-]+", " ", text.lower())).strip()


def classify_headline(headline: str, rules: list[dict[str, str]] | None = None) -> dict[str, Any]:
    text = _normalize(headline)
    rules = rules if rules is not None else _load_rules()
    matches = [r for r in rules if _normalize(str(r.get("keyword", ""))) in text]
    if not matches:
        return {"sentiment": NEUTRAL, "confidence": 0.0, "reason": "No relevant configured financial phrase", "matches": []}

    # Specific phrase wins over generic phrase. Explicit high-priority events
    # are stronger than broad terms such as "profit growth".
    high = [r for r in matches if str(r.get("priority", "")).upper() == "HIGH"]
    pool = high or matches
    sentiments = {str(r.get("sentiment", "")).upper() for r in pool}

    # If both directions are present, use local modifier/context rather than
    # guessing. Otherwise an ambiguous conflict is deliberately NEUTRAL.
    if POSITIVE in sentiments and NEGATIVE in sentiments:
        words = set(text.split())
        pos_mod = len(words & _POSITIVE_MODIFIERS)
        neg_mod = len(words & _NEGATIVE_MODIFIERS)
        if pos_mod > neg_mod:
            sentiment = POSITIVE
        elif neg_mod > pos_mod:
            sentiment = NEGATIVE
        else:
            return {"sentiment": NEUTRAL, "confidence": 0.0, "reason": "Conflicting positive and negative headline signals", "matches": pool}
    elif POSITIVE in sentiments:
        sentiment = POSITIVE
    elif NEGATIVE in sentiments:
        sentiment = NEGATIVE
    else:
        sentiment = NEUTRAL

    confidence = 0.85 if high else 0.65
    return {"sentiment": sentiment, "confidence": confidence, "reason": f"Matched: {', '.join(str(r.get('keyword')) for r in pool[:3])}", "matches": pool}


def get_yahoo_news(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        news = yf.Ticker(f"{str(symbol).upper().replace('.NS', '')}.NS").news or []
    except Exception:
        return []
    return news[:limit]


def analyze_yahoo_news(symbol: str, limit: int = 10) -> dict[str, Any]:
    rules = _load_rules()
    for item in get_yahoo_news(symbol, limit=limit):
        content = item.get("content") if isinstance(item, dict) else None
        title = (content or {}).get("title") if isinstance(content, dict) else None
        title = title or item.get("title") if isinstance(item, dict) else None
        if not title:
            continue
        result = classify_headline(str(title), rules)
        if result["sentiment"] != NEUTRAL:
            return {**result, "headline": str(title), "symbol": symbol, "source": ((content or {}).get("provider", {}).get("displayName") if isinstance(content, dict) else None)}
    return {"sentiment": NEUTRAL, "confidence": 0.0, "reason": "No recent directional Yahoo Finance headline", "headline": "", "symbol": symbol, "source": "Yahoo Finance"}


def news_allows_trade(side: str, analysis: dict[str, Any]) -> bool:
    sentiment = str(analysis.get("sentiment", NEUTRAL)).upper()
    return (side.upper() == "BUY" and sentiment == POSITIVE) or (side.upper() == "SELL" and sentiment == NEGATIVE)
