"""Clean Dhan-only S1-S5 paper-trading engine."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import TRADING_START,LAST_ENTRY_TIME,MAX_TRADES_PER_STRATEGY_PER_DAY,DAILY_MAX_LOSS_PER_STRATEGY
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from data.sector_alignment import load_sector_map,calculate_sector_alignment
from market.dhan_data import configured,map_nifty500,market_quote,index_quote
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from strategy.nifty500_price_action_strategies import evaluate,STRATEGY_DEFINITIONS
IST=ZoneInfo("Asia/Kolkata");OUTPUT=Path("outputs");SIGNAL_FILE=OUTPUT/"signals.csv"
class MasterEngine:
    def __init__(self):
        self.price_data=PriceData();self.universe_engine=StockUniverse();self.paper_engine=PaperTradeEngine();self.journal=TradeJournal();self.scanner=self
        self.references=pd.DataFrame();self.sector_map=pd.DataFrame();self.last_snapshot={};self.last_signals=[];self.diagnostics=self._blank_diag();self.daily_counts={s:0 for s in STRATEGY_DEFINITIONS};self.daily_pnl_by_strategy={s:0.0 for s in STRATEGY_DEFINITIONS};self._session_date=None;self._refresh_reference_data(True);self._restore_daily_limits()
    @staticmethod
    def now():return datetime.now(IST)
    @property
    def daily_pnl(self):return round(sum(self.daily_pnl_by_strategy.values()),2)
    def _blank_diag(self):return {"timestamp":None,"strategy":"S1-S5","strategy_version":"clean-dhan-v1","stocks_scanned":0,"reference_data_count":0,"market_data_coverage":"0/500","nifty500_change_pct":None,"sector_change_pct":None,"sector_available":False,"sector_mapping":"0/500","sector_priced":"0/500","positive_sectors":0,"negative_sectors":0,"sector_count":0,"ad_ratio":None,"ad_advances":0,"ad_declines":0,"ad_coverage":"0/500","buy_alignment":False,"sell_alignment":False,"final_signals":0,"signals_by_strategy":{s:0 for s in STRATEGY_DEFINITIONS},"rejections":{},"strategy_rejections":{s:{} for s in STRATEGY_DEFINITIONS},"market_data_source":"DHAN_ONLY","trade_path_status":"BLOCKED"}
    def _refresh_reference_data(self,force=False):
        today=self.now().date()
        if not force and self._session_date==today and len(self.references)==500:return
        try:u=self.universe_engine.get_dataframe(refresh=force)
        except Exception:u=pd.DataFrame()
        if u is None or u.empty or "Symbol" not in u.columns:self.references=pd.DataFrame();self.diagnostics["rejections"]["universe"]="NIFTY500_UNIVERSE_UNAVAILABLE";return
        u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);u=u.drop_duplicates("Symbol").head(500)
        try:r=ReferenceStore(u).prepare()
        except Exception:r=pd.DataFrame()
        self.references=r if r is not None else pd.DataFrame();self.sector_map=load_sector_map(u,refresh=force) if not u.empty else pd.DataFrame();self._session_date=today
        if len(self.references)!=500:self.diagnostics["rejections"]["reference"]=f"REFERENCE_INCOMPLETE_{len(self.references)}/500"
        if len(self.sector_map)!=500:self.diagnostics["rejections"]["sector_mapping"]=f"SECTOR_MAPPING_INCOMPLETE_{len(self.sector_map)}/500"
    def prepare_reference_data(self,force=False):self._refresh_reference_data(force);return self.references
    def prepare_opening_candidates(self,force=False):
        self._refresh_reference_data(force);return self.references[[c for c in ["Symbol","TodayOpen","PDH","PDL","PreviousDayClose"] if c in self.references.columns]].copy()
    def _restore_daily_limits(self):
        try:
            t=self.journal.get_trades()
            if t.empty or "entry_time" not in t.columns:return
            d=pd.to_datetime(t["entry_time"],errors="coerce")
            for _,r in t.loc[d.dt.date==self.now().date()].iterrows():
                s=str(r.get("strategy","")).upper();
                if s in self.daily_counts:self.daily_counts[s]+=1;self.daily_pnl_by_strategy[s]+=float(r.get("pnl",0) or 0)
        except Exception:pass
    def _market_snapshot(self):
        self._refresh_reference_data()
        blocked={"intraday":{},"prices":pd.DataFrame(),"sector":{},"nifty_change":None,"ad_ratio":None,"ad_complete":False,"buy_alignment":False,"sell_alignment":False,"dhan_quotes":{},"verified":False}
        if len(self.references)!=500 or not configured():
            self.diagnostics["rejections"]["market_data"]="DHAN_OR_REFERENCE_UNAVAILABLE";self.last_snapshot=blocked;self._write_diagnostics();return blocked
        symbols=self.references["Symbol"].astype(str).str.upper().tolist();mapping=map_nifty500(symbols)
        if len(mapping)!=500:self.diagnostics["rejections"]["mapping"]=f"DHAN_MAPPING_{len(mapping)}/500";self.last_snapshot=blocked;return blocked
        quotes=market_quote(mapping,cache_seconds=5)
        if len(quotes)!=500:self.diagnostics["rejections"]["market_data"]=f"DHAN_QUOTES_{len(quotes)}/500";self.last_snapshot=blocked;return blocked
        prices=quotes[["Symbol","LTP","PreviousClose","change_pct"]].copy();prices["change_pct"]=pd.to_numeric(prices["change_pct"],errors="coerce")
        if prices["change_pct"].isna().any():self.diagnostics["rejections"]["market_data"]="DHAN_CHANGE_INVALID";self.last_snapshot=blocked;return blocked
        adv=int((prices["change_pct"]>0).sum());dec=int((prices["change_pct"]<0).sum());ad=adv/dec if dec else float("inf")
        sector=calculate_sector_alignment(prices,self.sector_map) if len(self.sector_map)==500 else {"available":False}
        try:iq=index_quote("NIFTY 500");nifty=float(iq["NetChange"])/float(iq["PreviousClose"])*100 if iq else float(prices["change_pct"].mean())
        except Exception:nifty=float(prices["change_pct"].mean())
        pos=int(sector.get("positive_sectors",0) or 0);neg=int(sector.get("negative_sectors",0) or 0);sector_change=float(sector.get("alignment_pct",0) or 0)
        buy=bool(nifty>0 and ad>1 and pos>neg);sell=bool(nifty<0 and ad<1 and neg>pos)
        qmap={str(r["Symbol"]).upper():r.to_dict() for _,r in quotes.iterrows()}
        snap={"intraday":{},"prices":prices,"sector":{**sector,"positive_sectors":pos,"negative_sectors":neg,"alignment_pct":sector_change},"nifty_change":nifty,"ad_ratio":ad,"ad_complete":True,"buy_alignment":buy,"sell_alignment":sell,"dhan_quotes":qmap,"verified":True}
        self.last_snapshot=snap;self.diagnostics.update({"timestamp":self.now().isoformat(timespec="seconds"),"stocks_scanned":500,"reference_data_count":500,"market_data_coverage":"500/500","nifty500_change_pct":nifty,"sector_change_pct":sector_change,"sector_available":bool(sector.get("available")),"sector_mapping":"500/500","sector_priced":"500/500","positive_sectors":pos,"negative_sectors":neg,"sector_count":int(sector.get("sector_count",0) or 0),"ad_ratio":ad,"ad_advances":adv,"ad_declines":dec,"ad_coverage":"500/500","buy_alignment":buy,"sell_alignment":sell,"market_data_source":"DHAN_ONLY","trade_path_status":"READY" if buy or sell else "BLOCKED"})
        return snap
    def _candidate_symbols(self,snap):
        out=[]
        for _,r in self.references.iterrows():
            s=str(r["Symbol"]).upper();q=snap["dhan_quotes"].get(s)
            if not q:continue
            op,pdh,pdl,ltp,hi,lo=map(float,(q["TodayOpen"],r["PDH"],r["PDL"],q["LTP"],q["TodayHigh"],q["TodayLow"]))
            near_break=(hi>pdh or lo<pdl or ltp>pdh or ltp<pdl or (hi>0 and ltp>=hi*0.995) or (lo>0 and ltp<=lo*1.005))
            if near_break or (op>pdh and lo<=pdh) or (op<pdl and hi>=pdl) or (pdl<op<pdh and (lo<=pdl or hi>=pdh)):out.append(s)
        return out
    def _evaluate_stock(self,symbol,ref,snap):
        q=snap["dhan_quotes"].get(symbol);d=snap["intraday"].get(symbol)
        if not q or d is None or d.empty:return []
        d=self.price_data.today_only(d)
        if len(d)<1:return []
        prev=d.iloc[-1];pre=d.iloc[:-1];pdh,pdl=float(ref["PDH"]),float(ref["PDL"]);op,hi,lo,ltp=map(float,(q["TodayOpen"],q["TodayHigh"],q["TodayLow"],q["LTP"]))
        prior_high=float(pre["High"].max()) if not pre.empty else None;prior_low=float(pre["Low"].min()) if not pre.empty else None
        pull_low=float(pre["Low"].min()) if not pre.empty else None;pull_high=float(pre["High"].max()) if not pre.empty else None
        buy_break=bool(not pre.empty and (pre["High"]>pdh).any());sell_break=bool(not pre.empty and (pre["Low"]<pdl).any())
        common={"nifty500_change_pct":snap["nifty_change"],"sector_alignment_pct":snap["sector"].get("alignment_pct",0),"ad_ratio":snap["ad_ratio"],"ad_coverage":500,"positive_sectors":snap["sector"].get("positive_sectors",0),"negative_sectors":snap["sector"].get("negative_sectors",0),"previous_candle_open":float(prev["Open"]),"previous_candle_close":float(prev["Close"]),"symbol":symbol,"side":"BUY","ltp":ltp,"today_open":op,"pdh":pdh,"pdl":pdl,"today_low":lo,"today_high":hi,"prior_intraday_high":prior_high,"prior_intraday_low":prior_low,"pullback_low":pull_low,"pullback_high":pull_high,"breakout_seen":buy_break}
        out=[]
        for side in ("BUY","SELL"):
            if (side=="BUY" and not snap["buy_alignment"]) or (side=="SELL" and not snap["sell_alignment"]):continue
            common["side"]=side;common["breakout_seen"]=buy_break if side=="BUY" else sell_break
            for strategy in STRATEGY_DEFINITIONS:
                try:sig=evaluate(strategy,**common)
                except (TypeError,ValueError,KeyError):sig=None
                if sig:
                    row=sig.to_dict();row.update({"strategy_name":STRATEGY_DEFINITIONS[strategy]["name"],"today_open":op,"today_low":lo,"today_high":hi,"pdh":pdh,"pdl":pdl,"previous_day_close":float(ref["PreviousDayClose"]),"entry_time":self.now().isoformat(timespec="seconds"),"signal_status":"ELIGIBLE","price_source":"Dhan"});out.append(row)
        return out
    def scan(self):
        snap=self._market_snapshot();signals=[]
        if not snap.get("verified"):self.last_signals=[];self.diagnostics["final_signals"]=0;self._write_diagnostics();return []
        candidates=self._candidate_symbols(snap)
        if candidates:
            fresh=self.price_data.get_multi_1m(candidates)
            snap["intraday"]=fresh
            for _,ref in self.references[self.references["Symbol"].isin(candidates)].iterrows():signals.extend(self._evaluate_stock(str(ref["Symbol"]).upper(),ref,snap))
        self._write_signal_ledger(signals);selected=[];used=set();priority={"S1":5,"S2":4,"S3":4,"S4":3,"S5":2}
        for sig in sorted(signals,key=lambda x:(-priority.get(str(x.get("strategy","")),0),str(x.get("symbol","")))):
            s=sig["strategy"]
            if s in used or self.daily_counts[s]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[s]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            selected.append(sig);used.add(s)
        self.last_signals=selected;self.diagnostics["final_signals"]=len(selected);self.diagnostics["signals_by_strategy"]={s:sum(x.get("strategy")==s for x in selected) for s in STRATEGY_DEFINITIONS};self._write_diagnostics();return selected
    def process_signals(self,signals):
        opened=[]
        for sig in signals:
            s=sig["strategy"]
            if self.daily_counts[s]>=MAX_TRADES_PER_STRATEGY_PER_DAY or self.daily_pnl_by_strategy[s]<=-DAILY_MAX_LOSS_PER_STRATEGY:continue
            result=self.paper_engine.open_trade({**sig,"approved":True,"strategy":s})
            if result.get("opened"):
                p=result.get("position")
                if p:self.daily_counts[s]+=1;self.journal.log_trade(p);opened.append(p)
        return opened
    def run_cycle(self):
        self.process_positions();hhmm=self.now().strftime("%H:%M")
        if hhmm<TRADING_START or hhmm>LAST_ENTRY_TIME:return []
        return self.process_signals(self.scan())
    def process_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8)
            if not live:continue
            closed=self.paper_engine.process_live_price(symbol,live["Close"],live["Datetime"],live.get("High"),live.get("Low"))
            if closed:
                s=str(closed.get("strategy","S1")).upper();self.daily_pnl_by_strategy[s]+=float(closed.get("pnl",0) or 0);self.journal.log_trade(closed)
        self._write_diagnostics()
    def square_off_all(self):
        out=[];now=self.now()
        for symbol in list(self.paper_engine.open_positions):
            live=self.price_data.get_latest_live_price(symbol,max_age_seconds=8)
            if live:out.append(self.paper_engine.close_position(symbol,live["Close"],now,"SQUARE_OFF_15:00"))
        for c in [x for x in out if x]:self.journal.log_trade(c)
        self._write_diagnostics();return out
    def _write_signal_ledger(self,signals):
        if not signals:return
        OUTPUT.mkdir(parents=True,exist_ok=True)
        try:
            new=pd.DataFrame(signals);new["logged_at"]=self.now().isoformat(timespec="seconds");old=pd.read_csv(SIGNAL_FILE) if SIGNAL_FILE.exists() else pd.DataFrame();pd.concat([old,new],ignore_index=True).drop_duplicates(subset=[c for c in ["strategy","symbol","side","entry"] if c in new.columns]).to_csv(SIGNAL_FILE,index=False)
        except Exception:pass
    def _write_diagnostics(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        try:(OUTPUT/"diagnostics.json").write_text(json.dumps(self.diagnostics,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        except Exception:pass
