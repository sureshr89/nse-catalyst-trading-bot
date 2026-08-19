"""Single market snapshot -> S1-S5 -> risk -> paper execution pipeline."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import TRADING_START,LAST_ENTRY_TIME,SCAN_INTERVAL_SECONDS,MAX_TRADES_PER_STRATEGY_PER_DAY,DAILY_MAX_LOSS_PER_STRATEGY
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map,calculate_sector_alignment
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from strategy.nifty500_price_action_strategies import evaluate,STRATEGY_DEFINITIONS
IST=ZoneInfo("Asia/Kolkata");OUTPUT=Path("outputs")
class MasterEngine:
    """One worker, one 15-second snapshot, five strategies, one paper journal."""
    def __init__(self):
        self.price_data=PriceData();self.universe_engine=StockUniverse();self.paper_engine=PaperTradeEngine();self.journal=TradeJournal();self.scanner=self
        self.references=pd.DataFrame();self.sector_map=pd.DataFrame();self.last_snapshot={};self.last_signals=[];self.diagnostics=self._empty_diagnostics();self.daily_counts={s:0 for s in STRATEGY_DEFINITIONS};self.daily_pnl_by_strategy={s:0.0 for s in STRATEGY_DEFINITIONS};self.cooldown_until=None;self._session_date=None
        self._refresh_reference_data(force=True);self._restore_daily_limits()
    @property
    def daily_pnl(self):return round(sum(self.daily_pnl_by_strategy.values()),2)
    @staticmethod
    def now():return datetime.now(IST)
    def _empty_diagnostics(self):return {"timestamp":None,"strategy":"S1-S5","strategy_version":"2026.08.19.v3","stocks_scanned":0,"reference_data_count":0,"market_data_coverage":"0/500","nifty500_change_pct":None,"sector_change_pct":None,"sector_available":False,"sector_mapping":"0/500","sector_priced":"0/500","ad_ratio":None,"ad_advances":0,"ad_declines":0,"ad_coverage":"0/500","buy_alignment":False,"sell_alignment":False,"final_signals":0,"signals_by_strategy":{s:0 for s in STRATEGY_DEFINITIONS},"rejections":{}}
    def _refresh_reference_data(self,force=False):
        today=self.now().date()
        if not force and self._session_date==today and not self.references.empty:return
        try:universe=self.universe_engine.get_dataframe(refresh=True)
        except Exception:universe=pd.DataFrame()
        if universe is None or universe.empty or "Symbol" not in universe.columns:
            self.references=pd.DataFrame();self.sector_map=pd.DataFrame();self.diagnostics["rejections"]["universe"]="NIFTY500_UNIVERSE_UNAVAILABLE";return
        universe=universe.copy();universe["Symbol"]=universe["Symbol"].astype(str).str.upper().str.strip();universe=universe.drop_duplicates("Symbol")
        if len(universe)<500:self.diagnostics["rejections"]["universe"]=f"NIFTY500_UNIVERSE_INCOMPLETE_{len(universe)}/500"
        universe=universe.head(500)
        try:refs=ReferenceStore(universe).prepare()
        except Exception:refs=pd.DataFrame()
        self.references=refs if refs is not None else pd.DataFrame()
        if len(self.references)<500:self.diagnostics["rejections"]["reference"] = f"REFERENCE_DATA_INCOMPLETE_{len(self.references)}/500"
        if not self.references.empty:self.references["Symbol"]=self.references["Symbol"].astype(str).str.upper().str.strip()
        try:self.sector_map=load_sector_map(universe,refresh=force)
        except Exception:self.sector_map=pd.DataFrame()
        if len(self.sector_map)<500:self.diagnostics["rejections"]["sector_mapping"]=f"SECTOR_MAPPING_INCOMPLETE_{len(self.sector_map)}/500"
        self._session_date=today
    def prepare_reference_data(self,force=False):self._refresh_reference_data(force=force);return self.references
    def prepare_opening_candidates(self,force=False):
        self._refresh_reference_data(force=force);snap=self._market_snapshot();rows=[]
        for _,r in self.references.iterrows():
            d=snap["intraday"].get(str(r["Symbol"]).upper())
            if d is None or d.empty:continue
            rows.append({"Symbol":str(r["Symbol"]).upper(),"TodayOpen":float(d.iloc[0]["Open"]),"PDH":float(r["PDH"]),"PDL":float(r["PDL"]),"PreviousDayClose":float(r["PreviousDayClose"])})
        return pd.DataFrame(rows)
    def _restore_daily_limits(self):
        try:
            trades=self.journal.get_trades()
            if trades.empty or "entry_time" not in trades.columns:return
            dates=pd.to_datetime(trades["entry_time"],errors="coerce")
            for _,row in trades.loc[dates.dt.date==self.now().date()].iterrows():
                s=str(row.get("strategy","")).upper().strip()
                if s in self.daily_counts:
                    self.daily_counts[s]+=1
                    try:self.daily_pnl_by_strategy[s]+=float(row.get("pnl",0) or 0)
                    except Exception:pass
        except Exception:pass
    def _market_snapshot(self):
        self._refresh_reference_data()
        if self.references.empty:
            self.last_snapshot={"intraday":{},"prices":pd.DataFrame(),"sector":{},"nifty_change":None,"ad_ratio":None,"ad_complete":False};self.diagnostics["ad_coverage"]="0/500";self._write_diagnostics();return self.last_snapshot
        symbols=self.references["Symbol"].drop_duplicates().tolist()
        try:intraday=self.price_data.get_multi_1m(symbols)
        except Exception:intraday={}
        available=sum(1 for s in symbols if s in intraday and not intraday[s].empty);rows=[]
        for _,ref in self.references.iterrows():
            symbol=str(ref["Symbol"]).upper();d=intraday.get(symbol)
            if d is None or d.empty:continue
            d=self.price_data.today_only(d)
            if d.empty:continue
            pdc=float(ref.get("PreviousDayClose",0) or 0);close=float(d.iloc[-1]["Close"]);change=((close-pdc)/pdc*100) if pdc else 0.0;rows.append({"Symbol":symbol,"change_pct":change})
        prices=pd.DataFrame(rows);sector=calculate_sector_alignment(prices,self.sector_map) if not self.sector_map.empty else {"available":False,"mapped":len(self.sector_map),"priced":len(prices),"coverage":f"{len(prices)}/500"};complete=len(prices)==500
        if complete:advances=int((prices["change_pct"]>0).sum());declines=int((prices["change_pct"]<0).sum());ad_ratio=advances/declines if declines else float("inf")
        else:advances=declines=0;ad_ratio=None
        try:nifty_change=self.price_data.get_index_change_pct("^CRSLDX")
        except Exception:nifty_change=None
        if nifty_change is None and complete:nifty_change=float(prices["change_pct"].mean())
        sector_change=sector.get("alignment_pct") if sector.get("available") else None;buy=bool(complete and sector.get("available") and nifty_change is not None and nifty_change>0 and sector_change>0 and ad_ratio>1);sell=bool(complete and sector.get("available") and nifty_change is not None and nifty_change<0 and sector_change<0 and ad_ratio<1)
        self.last_snapshot={"intraday":intraday,"prices":prices,"sector":sector,"nifty_change":nifty_change,"ad_ratio":ad_ratio,"ad_complete":complete};self.diagnostics.update({"timestamp":self.now().isoformat(timespec="seconds"),"stocks_scanned":len(symbols),"reference_data_count":len(self.references),"market_data_coverage":f"{available}/500","nifty500_change_pct":nifty_change,"sector_change_pct":sector_change,"sector_available":bool(sector.get("available")),"sector_mapping":f"{sector.get('mapped',0)}/500","sector_priced":f"{sector.get('priced',0)}/500","ad_ratio":ad_ratio,"ad_advances":advances,"ad_declines":declines,"ad_coverage":f"{len(prices)}/500","buy_alignment":buy,"sell_alignment":sell});return self.last_snapshot
    @staticmethod
    def _prior_range(d):
        if d is None or len(d)<2:return None,None
        p=d.iloc[:-1];return float(p["High"].max()),float(p["Low"].min())
    def _evaluate_stock(self,symbol,ref,d,snap):
        if d is None or d.empty:return []
        prev=d.iloc[-1];today_open=float(d.iloc[0]["Open"]);today_low=float(d["Low"].min());today_high=float(d["High"].max());ltp=float(prev["Close"]);pdh=float(ref["PDH"]);pdl=float(ref["PDL"]);pdc=float(ref["PreviousDayClose"]);prior_high,prior_low=self._prior_range(d);out=[]
        for side in ("BUY","SELL"):
            if side=="BUY" and (not snap["buy_alignment"] or float(prev["Close"])<=float(prev["Open"])):continue
            if side=="SELL" and (not snap["sell_alignment"] or float(prev["Close"])>=float(prev["Open"])):continue
            common={"nifty500_change_pct":snap["nifty_change"],"sector_alignment_pct":snap["sector"].get("alignment_pct"),"ad_ratio":snap["ad_ratio"],"ad_coverage":500,"previous_candle_open":float(prev["Open"]),"previous_candle_close":float(prev["Close"]),"symbol":symbol,"side":side,"ltp":ltp,"today_open":today_open,"pdh":pdh,"pdl":pdl,"today_low":today_low,"today_high":today_high,"prior_intraday_high":prior_high,"prior_intraday_low":prior_low,"pullback_low":today_low,"pullback_high":today_high,"breakout_seen":False,"pdh_swept":False,"pdl_swept":False}
            if len(d)>=2:
                pre=d.iloc[:-1];common["pdh_swept"]=bool((pre["Low"]<pdh).any());common["pdl_swept"]=bool((pre["High"]>pdl).any());common["breakout_seen"]=bool((pre["High"]>pdh).any() if side=="BUY" else (pre["Low"]<pdl).any());common["pullback_low"]=float(pre["Low"].min());common["pullback_high"]=float(pre["High"].max())
            for strategy in STRATEGY_DEFINITIONS:
                try:signal=evaluate(strategy,**common)
                except (TypeError,ValueError):signal=None
                if signal:
                    row=signal.to_dict();row.update({"strategy_name":STRATEGY_DEFINITIONS[strategy]["name"],"today_open":today_open,"today_low":today_low,"today_high":today_high,"pdh":pdh,"pdl":pdl,"previous_day_close":pdc,"entry_time":self.now().isoformat(timespec="seconds")});out.append(row)
        return out
    def scan(self):
        snap=self._market_snapshot();signals=[]
        if not snap["ad_complete"]:self.diagnostics["rejections"]["breadth"]="NIFTY500_BREADTH_INCOMPLETE"
        if not snap["sector"].get("available"):self.diagnostics["rejections"]["sector"]="SECTOR_ALIGNMENT_UNAVAILABLE"
        if not (snap["buy_alignment"] or snap["sell_alignment"]):self.diagnostics["rejections"]["market_alignment"]="NO_MASTER_ALIGNMENT"
        if snap["buy_alignment"] or snap["sell_alignment"]:
            for _,ref in self.references.iterrows():signals.extend(self._evaluate_stock(str(ref["Symbol"]).upper(),ref,snap["intraday"].get(str(ref["Symbol"]).upper()),snap))
        selected=[];used=set()
        for sig in signals:
            s=sig["strategy"]
            if s in used or self.daily_counts[s]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[s]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            used.add(s);selected.append(sig)
        self.last_signals=selected;self.diagnostics["final_signals"]=len(selected);self.diagnostics["signals_by_strategy"]={s:sum(x["strategy"]==s for x in selected) for s in STRATEGY_DEFINITIONS};self._write_diagnostics();return selected
    def process_signals(self,signals):
        opened=[]
        for sig in signals:
            s=sig["strategy"]
            if self.daily_counts[s]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[s]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            result=self.paper_engine.open_trade({**sig,"approved":True,"strategy":s})
            if not result.get("opened"):continue
            position=result.get("position")
            if position:self.daily_counts[s]+=1;self.journal.log_trade(position);opened.append(position)
        return opened
    def run_cycle(self):
        self.process_positions();hhmm=self.now().strftime("%H:%M")
        if hhmm<TRADING_START or hhmm>LAST_ENTRY_TIME:return []
        return self.process_signals(self.scan())
    def process_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8)
            if not live:continue
            closed=self.paper_engine.process_live_price(symbol,live.get("Close"),live.get("Datetime"),live.get("High"),live.get("Low"))
            if closed:
                s=str(closed.get("strategy","S1")).upper();self.daily_pnl_by_strategy[s]=round(self.daily_pnl_by_strategy.get(s,0.0)+float(closed.get("pnl",0) or 0),2);self.journal.log_trade(closed)
        self._write_diagnostics()
    def square_off_all(self):
        now=self.now();out=[]
        for symbol in list(self.paper_engine.open_positions):
            live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8);price=(live or {}).get("Close")
            if price:out.append(self.paper_engine.close_position(symbol,price,now,"SQUARE_OFF_15:00"))
        for closed in [x for x in out if x]:
            s=str(closed.get("strategy","S1")).upper();self.daily_pnl_by_strategy[s]=round(self.daily_pnl_by_strategy.get(s,0.0)+float(closed.get("pnl",0) or 0),2);self.journal.log_trade(closed)
        self._write_diagnostics();return out
    def _write_diagnostics(self):
        OUTPUT.mkdir(parents=True,exist_ok=True);payload=dict(self.diagnostics);payload["daily_counts"]=dict(self.daily_counts);payload["daily_pnl_by_strategy"]=dict(self.daily_pnl_by_strategy);payload["paper_mode"]=True;payload["refresh_seconds"]=SCAN_INTERVAL_SECONDS;(OUTPUT/"scanner_diagnostics.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
