"""Clean Dhan-only S1-S5 paper-trading engine."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import TRADING_START,LAST_ENTRY_TIME,MAX_TRADES_PER_STRATEGY_PER_DAY,DAILY_MAX_LOSS_PER_STRATEGY,MIN_DATA_COVERAGE_COUNT
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
        if not force and self._session_date==today and len(self.references)>=MIN_DATA_COVERAGE_COUNT:return
        try:u=self.universe_engine.get_dataframe(refresh=force)
        except Exception:u=pd.DataFrame()
        if u is None or u.empty or "Symbol" not in u.columns:self.references=pd.DataFrame();self.diagnostics["rejections"]["universe"]="NIFTY500_UNIVERSE_UNAVAILABLE";return
        u=u.copy();u["Symbol"]=u["Symbol"].astype(str).str.upper().str.strip().str.replace(".NS","",regex=False);u=u.drop_duplicates("Symbol")
        if len(u)!=500:
            self.references=pd.DataFrame();self.diagnostics["rejections"]["universe"]=f"NIFTY500_UNIVERSE_INCOMPLETE_{len(u)}/500";return
        try:r=ReferenceStore(u).prepare()
        except Exception:r=pd.DataFrame()
        self.references=r if r is not None else pd.DataFrame();self.sector_map=load_sector_map(u,refresh=force) if not u.empty else pd.DataFrame();self._session_date=today
        if len(self.references)<MIN_DATA_COVERAGE_COUNT:self.diagnostics["rejections"]["reference"]=f"REFERENCE_BELOW_95PCT_{len(self.references)}/500"
        if len(self.sector_map)<MIN_DATA_COVERAGE_COUNT:self.diagnostics["rejections"]["sector_mapping"]=f"SECTOR_MAPPING_BELOW_95PCT_{len(self.sector_map)}/500"
    def prepare_reference_data(self,force=False):self._refresh_reference_data(force);return self.references
    def prepare_opening_candidates(self,force=False):
        self._refresh_reference_data(force);return self.references[[c for c in ["Symbol","TodayOpen","PDH","PDL","PreviousDayClose"] if c in self.references.columns]].copy()
    def _restore_daily_limits(self):
        try:
            t=self.journal.get_trades()
            if t.empty or "entry_time" not in t.columns:return
            d=pd.to_datetime(t["entry_time"],errors="coerce")
            for _,r in t.loc[d.dt.date==self.now().date()].iterrows():
                s=str(r.get("strategy","")).upper()
                if s in self.daily_counts:self.daily_counts[s]+=1;self.daily_pnl_by_strategy[s]+=float(r.get("pnl",0) or 0)
        except Exception:pass
    def _market_snapshot(self):
        self._refresh_reference_data()
        blocked={"intraday":{},"prices":pd.DataFrame(),"sector":{},"nifty_change":None,"ad_ratio":None,"ad_complete":False,"buy_alignment":False,"sell_alignment":False,"dhan_quotes":{},"verified":False}
        if len(self.references)<MIN_DATA_COVERAGE_COUNT or len(self.sector_map)<MIN_DATA_COVERAGE_COUNT or not configured():
            self.diagnostics["rejections"]["market_data"]="DHAN_OR_REFERENCE_OR_SECTOR_BELOW_95PCT";self.last_snapshot=blocked;self._write_diagnostics();return blocked
        symbols=self.references["Symbol"].astype(str).str.upper().tolist();mapping=map_nifty500(symbols)
        mapping_symbols=set(mapping.Symbol.astype(str).str.upper()) if not mapping.empty else set()
        if len(mapping)<MIN_DATA_COVERAGE_COUNT or len(mapping_symbols)<MIN_DATA_COVERAGE_COUNT:
            self.diagnostics["rejections"]["mapping"]=f"DHAN_MAPPING_BELOW_95PCT_{len(mapping)}/500";self.last_snapshot=blocked;return blocked
        quotes=market_quote(mapping,cache_seconds=5)
        quote_symbols=set(quotes.Symbol.astype(str).str.upper()) if not quotes.empty else set()
        if len(quotes)<MIN_DATA_COVERAGE_COUNT or len(quote_symbols)<MIN_DATA_COVERAGE_COUNT:
            self.diagnostics["rejections"]["market_data"]=f"DHAN_QUOTES_BELOW_95PCT_{len(quotes)}/500";self.last_snapshot=blocked;return blocked
        prices=quotes[["Symbol","LTP","PreviousClose","change_pct"]].copy();prices["change_pct"]=pd.to_numeric(prices["change_pct"],errors="coerce");prices["PreviousClose"]=pd.to_numeric(prices["PreviousClose"],errors="coerce")
        prices=prices.dropna(subset=["change_pct","PreviousClose"]);prices=prices[prices["PreviousClose"]>0].drop_duplicates("Symbol")
        if len(prices)<MIN_DATA_COVERAGE_COUNT:
            self.diagnostics["rejections"]["market_data"]=f"DHAN_VALID_PRICES_BELOW_95PCT_{len(prices)}/500";self.last_snapshot=blocked;return blocked
        adv=int((prices["change_pct"]>0).sum());dec=int((prices["change_pct"]<0).sum());ad=adv/dec if dec else float("inf")
        sector=calculate_sector_alignment(prices,self.sector_map)
        if not bool(sector.get("available")) or int(sector.get("priced",0) or 0)<MIN_DATA_COVERAGE_COUNT:
            self.diagnostics["rejections"]["sector"]=f"SECTOR_DATA_BELOW_95PCT_{sector.get('priced',0)}/500";self.last_snapshot=blocked;return blocked
        iq=index_quote("NIFTY 500")
        if not isinstance(iq,dict) or not iq.get("LTP") or not iq.get("PreviousClose"):
            self.diagnostics["rejections"]["nifty500"]="DHAN_NIFTY500_INDEX_UNAVAILABLE";self.last_snapshot=blocked;return blocked
        nifty=float(iq["NetChange"])/float(iq["PreviousClose"])*100
        pos=int(sector.get("positive_sectors",0) or 0);neg=int(sector.get("negative_sectors",0) or 0);sector_change=float(sector.get("alignment_pct",0) or 0)
        buy=bool(nifty>0 and ad>1 and pos>neg);sell=bool(nifty<0 and ad<1 and neg>pos)
        qmap={str(r["Symbol"]).upper():r.to_dict() for _,r in quotes.iterrows()}
        coverage=len(prices)
        snap={"intraday":{},"prices":prices,"sector":{**sector,"positive_sectors":pos,"negative_sectors":neg,"alignment_pct":sector_change},"nifty_change":nifty,"ad_ratio":ad,"ad_complete":coverage>=MIN_DATA_COVERAGE_COUNT,"buy_alignment":buy,"sell_alignment":sell,"dhan_quotes":qmap,"verified":True}
        self.last_snapshot=snap;self.diagnostics.update({"timestamp":self.now().isoformat(timespec="seconds"),"stocks_scanned":coverage,"reference_data_count":len(self.references),"market_data_coverage":f"{coverage}/500","nifty500_change_pct":nifty,"sector_change_pct":sector_change,"sector_available":True,"sector_mapping":f"{len(self.sector_map)}/500","sector_priced":f"{int(sector.get('priced',0))}/500","positive_sectors":pos,"negative_sectors":neg,"sector_count":int(sector.get("sectors",0) or 0),"ad_ratio":ad,"ad_advances":adv,"ad_declines":dec,"ad_coverage":f"{coverage}/500","buy_alignment":buy,"sell_alignment":sell,"market_data_source":"DHAN_ONLY","trade_path_status":"READY" if buy or sell else "BLOCKED"})
        return snap
