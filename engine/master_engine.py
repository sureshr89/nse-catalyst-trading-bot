"""Single market snapshot -> S1-S5 -> risk -> paper execution pipeline."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import TRADING_START, LAST_ENTRY_TIME, SCAN_INTERVAL_SECONDS, MAX_TRADES_PER_STRATEGY_PER_DAY, DAILY_MAX_LOSS_PER_STRATEGY
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map, calculate_sector_alignment
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from strategy.nifty500_price_action_strategies import evaluate, STRATEGY_DEFINITIONS
IST = ZoneInfo("Asia/Kolkata")
OUTPUT = Path("outputs")
SIGNAL_FILE = OUTPUT / "signals.csv"

class MasterEngine:
    """One worker, one common market gate, five paper strategies."""
    def __init__(self):
        self.price_data=PriceData(); self.universe_engine=StockUniverse(); self.paper_engine=PaperTradeEngine(); self.journal=TradeJournal(); self.scanner=self
        self.references=pd.DataFrame(); self.sector_map=pd.DataFrame(); self.last_snapshot={}; self.last_signals=[]; self.diagnostics=self._empty_diagnostics()
        self.daily_counts={s:0 for s in STRATEGY_DEFINITIONS}; self.daily_pnl_by_strategy={s:0.0 for s in STRATEGY_DEFINITIONS}; self.cooldown_until=None; self._session_date=None
        self._refresh_reference_data(force=True); self._restore_daily_limits()
    @property
    def daily_pnl(self): return round(sum(self.daily_pnl_by_strategy.values()),2)
    @staticmethod
    def now(): return datetime.now(IST)
    def _empty_diagnostics(self):
        return {"timestamp":None,"strategy":"S1-S5","strategy_version":"2026.08.20.v4","stocks_scanned":0,"reference_data_count":0,"market_data_coverage":"0/500","nifty500_change_pct":None,"sector_change_pct":None,"sector_available":False,"sector_mapping":"0/500","sector_priced":"0/500","ad_ratio":None,"ad_advances":0,"ad_declines":0,"ad_coverage":"0/500","buy_alignment":False,"sell_alignment":False,"final_signals":0,"signals_by_strategy":{s:0 for s in STRATEGY_DEFINITIONS},"rejections":{},"market_data_source":"UNKNOWN"}
    def _refresh_reference_data(self,force=False):
        today=self.now().date()
        if not force and self._session_date==today and not self.references.empty:return
        try: universe=self.universe_engine.get_dataframe(refresh=force)
        except Exception: universe=pd.DataFrame()
        if universe is None or universe.empty or "Symbol" not in universe.columns:
            self.references=pd.DataFrame(); self.sector_map=pd.DataFrame(); self.diagnostics["rejections"]["universe"]="NIFTY500_UNIVERSE_UNAVAILABLE"; return
        universe=universe.copy(); universe["Symbol"]=universe["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False); universe=universe.drop_duplicates("Symbol").head(500)
        if len(universe)<500:self.diagnostics["rejections"]["universe"]=f"NIFTY500_UNIVERSE_INCOMPLETE_{len(universe)}/500"
        try: refs=ReferenceStore(universe).prepare()
        except Exception: refs=pd.DataFrame()
        self.references=refs if refs is not None else pd.DataFrame()
        if not self.references.empty and "Symbol" in self.references.columns:self.references["Symbol"]=self.references["Symbol"].astype(str).str.upper().str.strip()
        if len(self.references)<500:self.diagnostics["rejections"]["reference"]=f"REFERENCE_DATA_INCOMPLETE_{len(self.references)}/500"
        try:self.sector_map=load_sector_map(universe,refresh=force)
        except Exception:self.sector_map=pd.DataFrame()
        if len(self.sector_map)<500:self.diagnostics["rejections"]["sector_mapping"]=f"SECTOR_MAPPING_INCOMPLETE_{len(self.sector_map)}/500"
        self._session_date=today
    def prepare_reference_data(self,force=False): self._refresh_reference_data(force=force); return self.references
    def prepare_opening_candidates(self,force=False):
        self._refresh_reference_data(force=force); snap=self._market_snapshot(); rows=[]
        for _,ref in self.references.iterrows():
            symbol=str(ref["Symbol"]).upper(); d=snap.get("intraday",{}).get(symbol)
            if d is None or d.empty:continue
            rows.append({"Symbol":symbol,"TodayOpen":float(d.iloc[0]["Open"]),"PDH":float(ref["PDH"]),"PDL":float(ref["PDL"]),"PreviousDayClose":float(ref["PreviousDayClose"])})
        return pd.DataFrame(rows)
    def _restore_daily_limits(self):
        try:
            trades=self.journal.get_trades()
            if trades.empty or "entry_time" not in trades.columns:return
            dates=pd.to_datetime(trades["entry_time"],errors="coerce")
            for _,row in trades.loc[dates.dt.date==self.now().date()].iterrows():
                strategy=str(row.get("strategy","")).upper().strip()
                if strategy in self.daily_counts:
                    self.daily_counts[strategy]+=1
                    try:self.daily_pnl_by_strategy[strategy]+=float(row.get("pnl",0) or 0)
                    except Exception:pass
        except Exception:pass
    def _market_snapshot(self):
        self._refresh_reference_data()
        if self.references.empty:
            self.last_snapshot={"intraday":{},"prices":pd.DataFrame(),"sector":{},"nifty_change":None,"ad_ratio":None,"ad_complete":False,"buy_alignment":False,"sell_alignment":False,"dhan_quotes":{}}
            self.diagnostics["ad_coverage"]="0/500"; self._write_diagnostics(); return self.last_snapshot
        symbols=self.references["Symbol"].drop_duplicates().tolist()
        try: intraday=self.price_data.get_multi_1m(symbols)
        except Exception: intraday={}
        available=sum(1 for s in symbols if s in intraday and not intraday[s].empty)
        rows=[]
        for _,ref in self.references.iterrows():
            symbol=str(ref["Symbol"]).upper(); d=intraday.get(symbol)
            if d is None or d.empty:continue
            d=self.price_data.today_only(d)
            if d.empty:continue
            pdc=float(ref.get("PreviousDayClose",0) or 0); close=float(d.iloc[-1]["Close"]); change=((close-pdc)/pdc*100) if pdc else 0.0
            rows.append({"Symbol":symbol,"change_pct":change})
        prices=pd.DataFrame(rows)
        sector=calculate_sector_alignment(prices,self.sector_map) if not self.sector_map.empty else {"available":False,"mapped":len(self.sector_map),"priced":len(prices),"coverage":f"{len(prices)}/500"}
        complete=len(prices)==500
        if complete:
            advances=int((prices["change_pct"]>0).sum()); declines=int((prices["change_pct"]<0).sum()); ad_ratio=advances/declines if declines else float("inf")
        else: advances=declines=0; ad_ratio=None
        try:nifty_change=self.price_data.get_index_change_pct("^CRSLDX")
        except Exception:nifty_change=None
        if nifty_change is None and complete:nifty_change=float(prices["change_pct"].mean())
        sector_change=sector.get("alignment_pct") if sector.get("available") else None
        buy=bool(complete and sector.get("available") and nifty_change is not None and nifty_change>0 and sector_change is not None and sector_change>0 and ad_ratio>1)
        sell=bool(complete and sector.get("available") and nifty_change is not None and nifty_change<0 and sector_change is not None and sector_change<0 and ad_ratio<1)
        # CRITICAL: use Dhan's current LTP/OHLC for live entry/SL/TP calculations when configured.
        # Completed 1-minute candles remain the confirmation layer; Dhan is the authoritative live price.
        dhan_quotes={}
        try:
            from market.dhan_data import configured, map_nifty500, market_quote
            if configured():
                mapping=map_nifty500(symbols)
                if not mapping.empty:
                    q=market_quote(mapping,cache_seconds=10)
                    if not q.empty:
                        dhan_quotes={str(r["Symbol"]).upper():r for r in q.to_dict("records")}
                        self.diagnostics["market_data_source"]="DHAN_OHLC_LTP"
                    else:self.diagnostics["market_data_source"]="YAHOO_1M_DHAN_UNAVAILABLE"
            else:self.diagnostics["market_data_source"]="YAHOO_1M"
        except Exception:self.diagnostics["market_data_source"]="YAHOO_1M_DHAN_ERROR"
        self.last_snapshot={"intraday":intraday,"prices":prices,"sector":sector,"nifty_change":nifty_change,"ad_ratio":ad_ratio,"ad_complete":complete,"buy_alignment":buy,"sell_alignment":sell,"dhan_quotes":dhan_quotes}
        self.diagnostics.update({"timestamp":self.now().isoformat(timespec="seconds"),"stocks_scanned":len(symbols),"reference_data_count":len(self.references),"market_data_coverage":f"{available}/500","nifty500_change_pct":nifty_change,"sector_change_pct":sector_change,"sector_available":bool(sector.get("available")),"sector_mapping":f"{sector.get('mapped',0)}/500","sector_priced":f"{sector.get('priced',0)}/500","ad_ratio":ad_ratio,"ad_advances":advances,"ad_declines":declines,"ad_coverage":f"{len(prices)}/500","buy_alignment":buy,"sell_alignment":sell})
        return self.last_snapshot
    @staticmethod
    def _prior_range(d):
        if d is None or len(d)<2:return None,None
        previous=d.iloc[:-1]; return float(previous["High"].max()),float(previous["Low"].min())
    def _evaluate_stock(self,symbol,ref,d,snap):
        if d is None or d.empty:return []
        symbol=str(symbol).upper(); prev=d.iloc[-1]; dhan=snap.get("dhan_quotes",{}).get(symbol,{})
        today_open=float(dhan.get("TodayOpen") or d.iloc[0]["Open"]); today_low=float(dhan.get("TodayLow") or d["Low"].min()); today_high=float(dhan.get("TodayHigh") or d["High"].max()); ltp=float(dhan.get("LTP") or prev["Close"])
        pdh=float(ref["PDH"]); pdl=float(ref["PDL"]); pdc=float(ref["PreviousDayClose"]); prior_high,prior_low=self._prior_range(d); out=[]
        for side in ("BUY","SELL"):
            if side=="BUY" and (not snap["buy_alignment"] or float(prev["Close"])<=float(prev["Open"])):continue
            if side=="SELL" and (not snap["sell_alignment"] or float(prev["Close"])>=float(prev["Open"])):continue
            common={"nifty500_change_pct":snap["nifty_change"],"sector_alignment_pct":snap["sector"].get("alignment_pct"),"ad_ratio":snap["ad_ratio"],"ad_coverage":500,"previous_candle_open":float(prev["Open"]),"previous_candle_close":float(prev["Close"]),"symbol":symbol,"side":side,"ltp":ltp,"today_open":today_open,"pdh":pdh,"pdl":pdl,"today_low":today_low,"today_high":today_high,"prior_intraday_high":prior_high,"prior_intraday_low":prior_low,"pullback_low":today_low,"pullback_high":today_high,"breakout_seen":False,"pdh_swept":False,"pdl_swept":False}
            if len(d)>=2:
                pre=d.iloc[:-1]; common["pdh_swept"]=bool((pre["Low"]<pdh).any() or (pre["High"]>pdh).any()); common["pdl_swept"]=bool((pre["Low"]<pdl).any() or (pre["High"]>pdl).any()); common["breakout_seen"]=bool((pre["High"]>pdh).any() if side=="BUY" else (pre["Low"]<pdl).any()); common["pullback_low"]=float(pre["Low"].min()); common["pullback_high"]=float(pre["High"].max())
            for strategy in STRATEGY_DEFINITIONS:
                try:signal=evaluate(strategy,**common)
                except (TypeError,ValueError,KeyError):signal=None
                if signal:
                    row=signal.to_dict(); row.update({"strategy_name":STRATEGY_DEFINITIONS[strategy]["name"],"today_open":today_open,"today_low":today_low,"today_high":today_high,"pdh":pdh,"pdl":pdl,"previous_day_close":pdc,"entry_time":self.now().isoformat(timespec="seconds"),"signal_status":"ELIGIBLE","price_source":"Dhan" if dhan else "1m close"}); out.append(row)
        return out
    def _write_signal_ledger(self,signals):
        if not signals:return
        OUTPUT.mkdir(parents=True,exist_ok=True); new=pd.DataFrame(signals)
        if new.empty:return
        new["logged_at"]=self.now().isoformat(timespec="seconds")
        try:
            old=pd.read_csv(SIGNAL_FILE) if SIGNAL_FILE.exists() else pd.DataFrame(); key_cols=[c for c in ["strategy","symbol","side","entry"] if c in new.columns]
            if key_cols and not old.empty:
                old_keys=set(old[key_cols].astype(str).agg("|".join,axis=1)); new=new[~new[key_cols].astype(str).agg("|".join,axis=1).isin(old_keys)]
            if not new.empty:pd.concat([old,new],ignore_index=True).to_csv(SIGNAL_FILE,index=False)
        except Exception:pass
    def scan(self):
        snap=self._market_snapshot(); signals=[]
        if not snap.get("ad_complete"):self.diagnostics["rejections"]["breadth"]="NIFTY500_BREADTH_INCOMPLETE"
        if not snap.get("sector",{}).get("available"):self.diagnostics["rejections"]["sector"]="SECTOR_ALIGNMENT_UNAVAILABLE"
        if not (snap.get("buy_alignment") or snap.get("sell_alignment")):self.diagnostics["rejections"]["market_alignment"]="NO_MASTER_ALIGNMENT"
        if snap.get("buy_alignment") or snap.get("sell_alignment"):
            for _,ref in self.references.iterrows():
                symbol=str(ref["Symbol"]).upper(); signals.extend(self._evaluate_stock(symbol,ref,snap.get("intraday",{}).get(symbol),snap))
        self._write_signal_ledger(signals); selected=[]; used=set(); priority={"S1":5,"S2":4,"S3":4,"S4":3,"S5":2}; signals.sort(key=lambda x:(-priority.get(str(x.get("strategy","")),0),str(x.get("symbol",""))))
        for sig in signals:
            strategy=sig["strategy"]
            if strategy in used or self.daily_counts[strategy]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[strategy]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            selected.append(sig); used.add(strategy)
        self.last_signals=selected; self.diagnostics["final_signals"]=len(selected); self.diagnostics["signals_by_strategy"]={s:sum(x.get("strategy")==s for x in selected) for s in STRATEGY_DEFINITIONS}; self._write_diagnostics(); return selected
    def process_signals(self,signals):
        opened=[]
        for sig in signals:
            strategy=sig["strategy"]
            if self.daily_counts[strategy]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[strategy]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            result=self.paper_engine.open_trade({**sig,"approved":True,"strategy":strategy})
            if not result.get("opened"):continue
            position=result.get("position")
            if position:self.daily_counts[strategy]+=1; self.journal.log_trade(position); opened.append(position)
        return opened
    def run_cycle(self):
        self.process_positions(); hhmm=self.now().strftime("%H:%M")
        if hhmm<TRADING_START or hhmm>LAST_ENTRY_TIME:return []
        return self.process_signals(self.scan())
    def _dhan_live_map(self):
        try:
            from market.dhan_data import configured
            from market.nifty500_breadth import BREADTH
            if not configured():return {}
            snapshot=BREADTH.snapshot(); rows=snapshot.get("quote_rows")
            if rows is None or not hasattr(rows,"to_dict"):return {}
            return {str(r.get("Symbol","")).upper():r for r in rows.to_dict("records")}
        except Exception:return {}
    def process_positions(self):
        dhan_map=self._dhan_live_map()
        for symbol in list(self.paper_engine.open_positions):
            live=None
            if symbol in dhan_map:
                row=dhan_map[symbol]
                try:live={"Close":float(row.get("LTP")),"Datetime":self.now(),"High":float(row.get("TodayHigh")),"Low":float(row.get("TodayLow")),"price_source":"Dhan"}
                except (TypeError,ValueError):live=None
            if live is None:live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8)
            if not live:continue
            closed=self.paper_engine.process_live_price(symbol,live.get("Close"),live.get("Datetime"),live.get("High"),live.get("Low"))
            if closed:
                strategy=str(closed.get("strategy","S1")).upper(); self.daily_pnl_by_strategy[strategy]=round(self.daily_pnl_by_strategy.get(strategy,0.0)+float(closed.get("pnl",0) or 0),2); self.journal.log_trade(closed)
        self._write_diagnostics()
    def square_off_all(self):
        now=self.now(); dhan_map=self._dhan_live_map(); out=[]
        for symbol in list(self.paper_engine.open_positions):
            price=None
            if symbol in dhan_map:
                try:price=float(dhan_map[symbol].get("LTP"))
                except (TypeError,ValueError):price=None
            if price is None:
                live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8); price=(live or {}).get("Close")
            if price:out.append(self.paper_engine.close_position(symbol,price,now,"SQUARE_OFF_15:00"))
        for closed in [x for x in out if x]:
            strategy=str(closed.get("strategy","S1")).upper(); self.daily_pnl_by_strategy[strategy]=round(self.daily_pnl_by_strategy.get(strategy,0.0)+float(closed.get("pnl",0) or 0),2); self.journal.log_trade(closed)
        self._write_diagnostics(); return out
    def _write_diagnostics(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        try:(OUTPUT/"diagnostics.json").write_text(json.dumps(self.diagnostics,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        except Exception:pass
