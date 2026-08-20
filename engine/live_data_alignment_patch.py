"""Make Dhan the single authoritative live data source for price, A/D, sectors and S1-S5 gating."""
from datetime import datetime
import threading
import time
import pandas as pd

_QUOTE_LOCK = threading.RLock()
_QUOTE_CACHE = None
_QUOTE_CACHE_AT = 0.0
_QUOTE_CACHE_KEY = None
QUOTE_CACHE_SECONDS = 8.0


def _dhan_market_quote(mapping, cache_seconds=QUOTE_CACHE_SECONDS):
    """Fetch one complete Dhan quote snapshot; previous close = LTP - net_change."""
    global _QUOTE_CACHE, _QUOTE_CACHE_AT, _QUOTE_CACHE_KEY
    from market.dhan_data import configured, _post
    if mapping is None or mapping.empty or not configured(): return pd.DataFrame()
    ids = pd.to_numeric(mapping["SecurityId"], errors="coerce").dropna().astype(int).astype(str).tolist()
    expected_ids = set(ids); expected_symbols = set(mapping["Symbol"].astype(str).str.upper().str.strip())
    cache_key = tuple(sorted(expected_ids)); now = time.monotonic()
    with _QUOTE_LOCK:
        if _QUOTE_CACHE is not None and _QUOTE_CACHE_KEY == cache_key and now - _QUOTE_CACHE_AT <= cache_seconds:
            return _QUOTE_CACHE.copy()
    response = _post("/marketfeed/quote", {"NSE_EQ": [int(x) for x in ids]})
    data = response.get("data", {}).get("NSE_EQ", {}) if response else {}
    by_id = dict(zip(mapping["SecurityId"].astype(str), mapping["Symbol"].astype(str).str.upper().str.strip()))
    rows = []
    for sid, item in data.items():
        if str(sid) not in expected_ids or not isinstance(item, dict): continue
        ohlc = item.get("ohlc") or {}
        try:
            ltp=float(item.get("last_price") or 0); net=float(item.get("net_change") or 0)
            op=float(ohlc.get("open") or 0); hi=float(ohlc.get("high") or 0); lo=float(ohlc.get("low") or 0); close=float(ohlc.get("close") or 0); vol=float(item.get("volume") or 0)
            previous_close=ltp-net
            if ltp<=0 or previous_close<=0: continue
            rows.append({"Symbol":by_id[str(sid)],"SecurityId":str(sid),"LTP":ltp,"TodayOpen":op,"TodayHigh":hi,"TodayLow":lo,"TodayClose":close,"PreviousClose":previous_close,"NetChange":net,"Volume":vol,"change_pct":(ltp-previous_close)/previous_close*100.0,"UpdatedAt":datetime.now().isoformat(timespec="seconds"),"price_source":"DHAN_MARKETFEED_QUOTE"})
        except (TypeError,ValueError): continue
    result=pd.DataFrame(rows).drop_duplicates("SecurityId") if rows else pd.DataFrame()
    if result.empty:return result
    verified=(len(result)==len(expected_ids) and set(result["SecurityId"].astype(str))==expected_ids and set(result["Symbol"].astype(str).str.upper())==expected_symbols and result["LTP"].notna().all() and result["PreviousClose"].notna().all() and (result["LTP"]>0).all() and (result["PreviousClose"]>0).all())
    if not verified:return pd.DataFrame()
    with _QUOTE_LOCK:_QUOTE_CACHE=result.copy();_QUOTE_CACHE_AT=time.monotonic();_QUOTE_CACHE_KEY=cache_key
    return result


def _blocked(reason):
    return {"intraday":{},"prices":pd.DataFrame(),"sector":{},"nifty_change":None,"ad_ratio":None,"ad_complete":False,"buy_alignment":False,"sell_alignment":False,"dhan_quotes":{},"block_reason":reason}


def install(MasterEngine):
    """Install one authoritative Dhan snapshot for the entire decision chain."""
    from market import dhan_data, nifty500_breadth
    dhan_data.market_quote=_dhan_market_quote
    nifty500_breadth.market_quote=_dhan_market_quote

    def aligned_snapshot(self):
        from market.nifty500_breadth import BREADTH
        self.diagnostics.setdefault("rejections", {})
        self.diagnostics["rejections"]={}
        verified=BREADTH.snapshot(force=False)
        if not verified.get("complete") or not verified.get("sector_complete"):
            reason=str(verified.get("reason") or "DHAN_VERIFICATION_FAILED")
            self.diagnostics.update({"market_data_source":"DHAN_VERIFICATION_FAILED","market_data_coverage":f"{verified.get('evaluated',0)}/500","ad_coverage":f"{verified.get('evaluated',0)}/500","sector_available":False,"market_snapshot":"BLOCKED","market_gate":"NO_ALIGNMENT"})
            self.diagnostics["rejections"]["market_data"]=reason
            snap=_blocked(reason); self.last_snapshot=snap; return snap
        quotes=verified.get("quote_rows")
        if not isinstance(quotes,pd.DataFrame) or len(quotes)!=500:
            reason=f"DHAN_QUOTE_ROWS_NOT_500_{len(quotes) if isinstance(quotes,pd.DataFrame) else 0}/500"
            self.diagnostics.update({"market_data_source":"DHAN_VERIFICATION_FAILED","market_data_coverage":reason,"market_snapshot":"BLOCKED","market_gate":"NO_ALIGNMENT"})
            self.diagnostics["rejections"]["market_data"]=reason
            snap=_blocked(reason); self.last_snapshot=snap; return snap

        prices=quotes[["Symbol","LTP","PreviousClose","NetChange","change_pct"]].copy()
        prices["LTP"]=pd.to_numeric(prices["LTP"],errors="coerce"); prices["PreviousClose"]=pd.to_numeric(prices["PreviousClose"],errors="coerce")
        prices["change_pct"]=(prices["LTP"]-prices["PreviousClose"])/prices["PreviousClose"]*100.0
        sector={"available":True,"mapped":int(verified.get("sector_mapped",0) or 0),"priced":int(verified.get("sector_priced",0) or 0),"coverage":str(verified.get("sector_coverage","0/500")),"alignment_pct":verified.get("sector_alignment_pct"),"positive_sectors":int(verified.get("positive_sectors",0) or 0),"negative_sectors":int(verified.get("negative_sectors",0) or 0),"unchanged_sectors":int(verified.get("unchanged_sectors",0) or 0),"sectors":int(verified.get("sector_count",0) or 0)}
        nifty_change=verified.get("nifty500_change_pct"); ad_ratio=verified.get("ad_ratio"); sector_change=sector["alignment_pct"]
        buy=bool(nifty_change is not None and nifty_change>0 and sector_change is not None and sector_change>0 and ad_ratio is not None and ad_ratio>1)
        sell=bool(nifty_change is not None and nifty_change<0 and sector_change is not None and sector_change<0 and ad_ratio is not None and ad_ratio<1)
        dhan_quotes={str(r["Symbol"]).upper().strip():r for r in quotes.to_dict("records")}
        try:intraday=self.price_data.get_multi_1m(list(dhan_quotes.keys()))
        except Exception:intraday={}
        snap={"intraday":intraday,"prices":prices,"sector":sector,"nifty_change":float(nifty_change) if nifty_change is not None else None,"ad_ratio":float(ad_ratio) if ad_ratio is not None else None,"ad_complete":True,"buy_alignment":buy,"sell_alignment":sell,"dhan_quotes":dhan_quotes,"verified":verified}
        # Critical: diagnostics must reference THIS exact cycle, not a previous snapshot.
        self.last_snapshot=snap
        self.diagnostics.update({"market_data_source":"DHAN_VERIFIED_500","market_data_coverage":"500/500","nifty500_change_pct":nifty_change,"sector_change_pct":sector_change,"sector_available":True,"sector_mapping":f"{sector['mapped']}/500","sector_priced":f"{sector['priced']}/500","sector_count":sector["sectors"],"positive_sectors":sector["positive_sectors"],"negative_sectors":sector["negative_sectors"],"unchanged_sectors":sector["unchanged_sectors"],"ad_ratio":ad_ratio,"ad_advances":int(verified.get("advances",0) or 0),"ad_declines":int(verified.get("declines",0) or 0),"ad_coverage":"500/500","buy_alignment":buy,"sell_alignment":sell,"market_snapshot":"PASS","market_gate":"BUY" if buy else "SELL" if sell else "NO_ALIGNMENT"})
        return snap
    MasterEngine._market_snapshot=aligned_snapshot
    MasterEngine._live_data_alignment_patch_installed=True
    return MasterEngine
