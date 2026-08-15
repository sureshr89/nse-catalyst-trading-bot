"""Deterministic Yahoo Finance headline sentiment; no LLM or paid API."""
from __future__ import annotations
import csv, re
from pathlib import Path
from typing import Any
import yfinance as yf

CSV_PATH = Path("data/news_sentiment_keywords.csv")
POSITIVE, NEGATIVE, NEUTRAL = "POSITIVE", "NEGATIVE", "NEUTRAL"
_NEG = {"weak","poor","lower","decline","declining","slow","slower","slowing","disappointing","miss","misses","below","cuts","cut","falls","fall","drops","drop","lost","loss"}
_POS = {"strong","robust","higher","accelerating","record","beats","beat","above","raises","raised","improves","improved","wins","won"}

def _rules():
    if not CSV_PATH.exists(): return []
    with CSV_PATH.open(encoding="utf-8", newline="") as f: rows=list(csv.DictReader(f))
    return sorted(rows,key=lambda r:len(str(r.get("keyword",""))),reverse=True)

def _norm(s): return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9%₹.$-]+"," ",str(s).lower())).strip()

def classify_headline(headline:str,rules=None)->dict[str,Any]:
    text=_norm(headline); rules=_rules() if rules is None else rules
    matches=[r for r in rules if _norm(r.get("keyword","")) in text]
    if not matches: return {"sentiment":NEUTRAL,"confidence":0.0,"reason":"No configured financial phrase","matches":[]}
    high=[r for r in matches if str(r.get("priority","")).upper()=="HIGH"]; pool=high or matches
    sentiments={str(r.get("sentiment","")).upper() for r in pool}; words=set(text.split())
    if POSITIVE in sentiments and NEGATIVE in sentiments:
        p=len(words&_POS); n=len(words&_NEG)
        if p==n: return {"sentiment":NEUTRAL,"confidence":0.0,"reason":"Conflicting headline signals","matches":pool}
        sentiment=POSITIVE if p>n else NEGATIVE
    elif POSITIVE in sentiments: sentiment=POSITIVE
    elif NEGATIVE in sentiments: sentiment=NEGATIVE
    else: sentiment=NEUTRAL
    return {"sentiment":sentiment,"confidence":0.85 if high else 0.65,"reason":"Matched: "+", ".join(r.get("keyword","") for r in pool[:3]),"matches":pool}

def _title(item):
    c=item.get("content") if isinstance(item,dict) else None
    return ((c or {}).get("title") if isinstance(c,dict) else None) or (item.get("title") if isinstance(item,dict) else None)

def analyze_yahoo_news(symbol:str,limit:int=10)->dict[str,Any]:
    try: news=yf.Ticker(f"{str(symbol).upper().replace('.NS','')}.NS").news or []
    except Exception: news=[]
    for item in news[:limit]:
        title=_title(item)
        if not title: continue
        result=classify_headline(title)
        if result["sentiment"]!=NEUTRAL:
            return {**result,"headline":title,"symbol":symbol,"source":"Yahoo Finance"}
    return {"sentiment":NEUTRAL,"confidence":0.0,"reason":"No recent directional Yahoo Finance headline","headline":"","symbol":symbol,"source":"Yahoo Finance"}

def news_allows_trade(side:str,analysis:dict[str,Any])->bool:
    s=str(analysis.get("sentiment",NEUTRAL)).upper(); side=side.upper()
    return (side=="BUY" and s==POSITIVE) or (side=="SELL" and s==NEGATIVE)
