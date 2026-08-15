"""Stateful NIFTY 500 scanner for PDH/PDL + Today's Open return strategy."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json, math
import pandas as pd
from config.settings import TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO, NIFTY500_MIN_CHANGE_PCT
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from market.live_price import get_current_market_price
from strategy.open_reversal_engine import OpenReversalEngine
from strategy.candidate_metrics import metrics, sort_key

INDIA_TZ=ZoneInfo("Asia/Kolkata")
MIN_MARKET_DATA_COVERAGE=0.95

class ScannerEngine:
    """Maintain BUY/SELL waiting states across 30-second control cycles."""
    def __init__(self):
        self.universe_engine=StockUniverse(); self.universe=self.universe_engine.get_dataframe(refresh=False)
        self.price_data=PriceData(); self.strategy=OpenReversalEngine(TRADING_START,LAST_ENTRY_TIME,RISK_REWARD_RATIO)
        self.references=pd.DataFrame(); self.opening_candidates=pd.DataFrame(); self.gap_analysis=pd.DataFrame(); self.universe_market_data={}; self.nifty500_market_data=pd.DataFrame(); self._prepared_date=None
        self._data_cache_at=None; self._nifty_cache_at=None; self._nifty_change=0.0; self._activated={"BUY":False,"SELL":False}; self._activated_at={"BUY":None,"SELL":None}; self.waiting={"BUY":{},"SELL":{}}; self.qualified={"BUY":{},"SELL":{}}; self.metrics_cache={}; self._load_waiting(); self.diagnostics=self._empty_diagnostics()
    @staticmethod
    def _empty_diagnostics():
        return {"timestamp":None,"stocks_scanned":0,"opening_setup_passed":0,"market_alignment_passed":0,"strategy_setup_passed":0,"final_signals":0,"gap_up_count":0,"gap_down_count":0,"gap_data_count":0,"nifty500_direction":"UNKNOWN","nifty500_change_pct":0.0,"nifty500_bullish":0,"nifty500_bearish":0,"nifty500_neutral":0,"nifty500_coverage":0,"market_data_coverage":0.0,"buy_waiting":0,"sell_waiting":0,"buy_qualified":0,"sell_qualified":0,"ranking":[],"rejections":{"missing_data":0,"opening_setup":0,"market_alignment":0,"strategy_setup":0}}
    @staticmethod
    def _today(): return pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d")
    @staticmethod
    def _candidate_id(symbol,side,today_open,pdh,pdl):
        return "|".join([pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d"),str(symbol).upper(),str(side).upper(),f"{float(today_open):.4f}",f"{float(pdh):.4f}",f"{float(pdl):.4f}"])
    def _waiting_path(self): return Path(__file__).resolve().parents[1]/"outputs"/"waiting_candidates.json"
    def _load_waiting(self):
        try:
            payload=json.loads(self._waiting_path().read_text(encoding="utf-8"))
            if payload.get("date")!=self._today(): return
            self.waiting=payload.get("waiting",{"BUY":{},"SELL":{}}); self.qualified=payload.get("qualified",{"BUY":{},"SELL":{}}); self._activated=payload.get("activated",{"BUY":False,"SELL":False}); self._activated_at=payload.get("activated_at",{"BUY":None,"SELL":None})
        except Exception: pass
    def _save_waiting(self):
        path=self._waiting_path(); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"date":self._today(),"updated_at":datetime.now(INDIA_TZ).isoformat(timespec="seconds"),"activated":self._activated,"activated_at":self._activated_at,"waiting":self.waiting,"qualified":self.qualified},indent=2,default=str),encoding="utf-8"); tmp.replace(path)
        except Exception as error: print("Could not persist waiting candidates:",error)
    def _write_diagnostics(self):
        self.diagnostics.update({"buy_waiting":len(self.waiting["BUY"]),"sell_waiting":len(self.waiting["SELL"]),"buy_qualified":len(self.qualified["BUY"]),"sell_qualified":len(self.qualified["SELL"])})
        payload=dict(self.diagnostics); payload["rejections"]=dict(self.diagnostics.get("rejections",{})); payload["timestamp"]=datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        path=Path(__file__).resolve().parents[1]/"outputs"/"scanner_diagnostics.json"; path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name("scanner_diagnostics.tmp")
        try: tmp.write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8"); tmp.replace(path)
        except Exception as error: print("Could not write diagnostics:",error)
    def _write_gap_analysis(self,rows):
        path=Path(__file__).resolve().parents[1]/"outputs"/"gap_analysis.csv"; path.parent.mkdir(parents=True,exist_ok=True)
        try: pd.DataFrame(rows).to_csv(path,index=False)
        except Exception as error: print("Could not write gap analysis:",error)
    def prepare_reference_data(self,force=False):
        today=self._today()
        if not force and self._prepared_date==today and not self.references.empty:return self.references
        self.universe=self.universe_engine.get_dataframe(refresh=True); refs=ReferenceStore(self.universe).prepare()
        if refs is None or refs.empty:self.references=pd.DataFrame(); self._prepared_date=None; return self.references
        self.references=refs; self._prepared_date=today; return refs
    def _industry_for_symbol(self,symbol):
        try:
            if "Symbol" in self.universe.columns and "Industry" in self.universe.columns:
                row=self.universe[self.universe["Symbol"].astype(str).str.upper().eq(str(symbol).upper())]
                if not row.empty:return str(row.iloc[0]["Industry"] or "UNKNOWN").strip() or "UNKNOWN"
        except Exception: pass
        return "UNKNOWN"
    def _market_snapshot(self,symbols):
        now=datetime.now(INDIA_TZ)
        if self._data_cache_at is not None and (now-self._data_cache_at).total_seconds()<55 and self.universe_market_data:return self.universe_market_data
        data=self.price_data.get_multi_1m(symbols); self.universe_market_data=data; self._data_cache_at=now; return data
    def _nifty_snapshot(self):
        now=datetime.now(INDIA_TZ)
        if self._nifty_cache_at is not None and (now-self._nifty_cache_at).total_seconds()<25:return self._nifty_change
        self.nifty500_market_data=self.price_data.get_index_1m("^CRSLDX"); change=self.price_data.get_index_change_pct("^CRSLDX")
        if change is None:return None
        self._nifty_change=float(change); self._nifty_cache_at=now; return self._nifty_change
    def _build_gap_board(self,references,market_data):
        rows=[]; gaps=[]
        for _,ref in references.iterrows():
            symbol=str(ref["Symbol"]).upper(); data=market_data.get(symbol)
            if data is None or data.empty: continue
            today=self.price_data.today_only(data)
            if today.empty: continue
            try: op=float(today.iloc[0]["Open"]); pdc=float(ref["PreviousDayClose"]); pdh=float(ref["PDH"]); pdl=float(ref["PDL"])
            except (TypeError,ValueError): continue
            industry=self._industry_for_symbol(symbol)
            if op>pdh: gap_type,setup,level="GAP_UP","OPEN_ABOVE_PDH",pdh
            elif op<pdl: gap_type,setup,level="GAP_DOWN","OPEN_BELOW_PDL",pdl
            else: gap_type,setup,level="INSIDE_PDH_PDL","NO_GAP_SETUP",None
            gap=op-level if level is not None else 0.0; gap_pct=gap/level*100 if level else 0.0; close_gap=op-pdc; close_gap_pct=close_gap/pdc*100 if pdc else 0.0
            gaps.append({"Symbol":symbol,"Industry":industry,"PreviousClose":round(pdc,4),"TodayOpen":round(op,4),"Gap":round(gap,4),"GapPercent":round(gap_pct,3),"GapFromPreviousClose":round(close_gap,4),"GapPercentFromPreviousClose":round(close_gap_pct,3),"GapType":gap_type,"PDH":round(pdh,4),"PDL":round(pdl,4),"PreparedAtIST":datetime.now(INDIA_TZ).isoformat(timespec="seconds")})
            if setup!="NO_GAP_SETUP": rows.append({"Symbol":symbol,"Industry":industry,"PDH":pdh,"PDL":pdl,"TodayOpen":op,"PreviousDayClose":pdc,"Gap":gap,"GapPercent":gap_pct,"GapFromPreviousClose":close_gap,"GapPercentFromPreviousClose":close_gap_pct,"GapType":gap_type,"OpeningSetup":setup})
        self.gap_analysis=pd.DataFrame(gaps).drop_duplicates("Symbol") if gaps else pd.DataFrame(); self.opening_candidates=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame(); self._write_gap_analysis(gaps)
        self.diagnostics["gap_data_count"]=len(self.gap_analysis); self.diagnostics["gap_up_count"]=int((self.gap_analysis.get("GapType",pd.Series(dtype=str))=="GAP_UP").sum()); self.diagnostics["gap_down_count"]=int((self.gap_analysis.get("GapType",pd.Series(dtype=str))=="GAP_DOWN").sum()); self.diagnostics["opening_setup_passed"]=len(self.opening_candidates); return self.opening_candidates
    def prepare_opening_candidates(self,force=False):
        refs=self.prepare_reference_data(force=force)
        if refs.empty:return pd.DataFrame()
        symbols=refs["Symbol"].astype(str).str.upper().drop_duplicates().tolist(); return self._build_gap_board(refs,self._market_snapshot(symbols))
    def _activate_side(self,side,change):
        active=change>=NIFTY500_MIN_CHANGE_PCT if side=="BUY" else change<=-NIFTY500_MIN_CHANGE_PCT
        if active and not self._activated[side]: self._activated[side]=True; self._activated_at[side]=datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        return active
    def _seed_and_update(self,side,change,market_data):
        active=self._activate_side(side,change)
        if not active and not self._activated[side]: return
        activation=pd.to_datetime(self._activated_at[side],errors="coerce") if self._activated_at[side] else None
        for _,row in self.opening_candidates.iterrows():
            symbol=str(row["Symbol"]).upper(); initial_side="BUY" if row["OpeningSetup"]=="OPEN_ABOVE_PDH" else "SELL" if row["OpeningSetup"]=="OPEN_BELOW_PDL" else None
            if initial_side!=side: continue
            candidate_id=self._candidate_id(symbol,side,row["TodayOpen"],row["PDH"],row["PDL"])
            if symbol not in self.waiting[side] and symbol not in self.qualified[side]:
                self.waiting[side][symbol]={"candidate_id":candidate_id,"symbol":symbol,"side":side,"today_open":float(row["TodayOpen"]),"pdh":float(row["PDH"]),"pdl":float(row["PDL"]),"previous_day_close":float(row["PreviousDayClose"]),"gap":float(row.get("Gap",0)),"gap_percent":float(row.get("GapPercent",0)),"industry":row.get("Industry","UNKNOWN"),"state":"WAITING_FOR_BREACH","created_at":datetime.now(INDIA_TZ).isoformat(timespec="seconds")}
            state=self.waiting[side].get(symbol)
            if not state: continue
            state.setdefault("candidate_id",candidate_id)
            data=market_data.get(symbol); today=self.price_data.today_only(data) if data is not None else pd.DataFrame()
            if today.empty: continue
            if activation is not None: today=today[today["Datetime"]>=activation]
            for _,candle in today.iterrows():
                before=dict(state); state=self.strategy.update_state(state,row["TodayOpen"],row["PDH"],row["PDL"],candle["Close"],candle["Datetime"].isoformat())
                if state.get("pdh_breached") and not before.get("pdh_breached") and side=="BUY": state["state"]="WAITING_FOR_OPEN"
                if state.get("pdl_breached") and not before.get("pdl_breached") and side=="SELL": state["state"]="WAITING_FOR_OPEN"
                if state.get("open_returned"): state["state"]="QUALIFIED"; state["qualified_close"]=float(candle["Close"]); state["qualified_at"]=candle["Datetime"].isoformat(); break
            if state.get("open_returned"): self.qualified[side][symbol]=state; self.waiting[side].pop(symbol,None)
            else:self.waiting[side][symbol]=state
    def _rank_qualified(self,side,market_data):
        rows=[]
        for symbol,state in list(self.qualified[side].items()):
            data=market_data.get(symbol); today=self.price_data.today_only(data) if data is not None else pd.DataFrame()
            if today.empty: continue
            if symbol not in self.metrics_cache:self.metrics_cache[symbol]=metrics(self.price_data,symbol,today)
            item=dict(state); item.update(self.metrics_cache[symbol]); rows.append(item)
        rows.sort(key=sort_key,reverse=True); return rows
    def _final_signals(self,change,market_data):
        signals=[]; ranking=[]
        for side in ("BUY","SELL"):
            if not self.strategy.market_aligned(side,change): continue
            for item in self._rank_qualified(side,market_data):
                symbol=item["symbol"]; current=get_current_market_price(symbol)
                if not current: continue
                entry=float(current["Close"]); open_price=float(item["today_open"])
                if side=="BUY" and entry<open_price: continue
                if side=="SELL" and entry>open_price: continue
                metric_values={"atr_pct":item.get("atr_pct",0),"metrics_calculated_at":item.get("metrics_calculated_at","")}
                signal=self.strategy.build_signal(symbol,side,entry,open_price,item["pdh"],item["pdl"],change,metric_values)
                if signal:
                    signal.update({"candidate_id":item.get("candidate_id"),"industry":item.get("industry","UNKNOWN"),"gap":item.get("gap",0),"gap_percent":item.get("gap_percent",0),"gap_type":"GAP_UP" if side=="BUY" else "GAP_DOWN","nifty500_universe":True,"candidate_state":"QUALIFIED","priority_rank":len(ranking)+1})
                    ranking.append({"priority":len(ranking)+1,"candidate_id":item.get("candidate_id"),"symbol":symbol,"side":side,"atr_pct":item.get("atr_pct",0)})
                    signals.append(signal)
        self.diagnostics["ranking"]=ranking; return signals
    def scan(self):
        self.diagnostics=self._empty_diagnostics(); refs=self.prepare_reference_data()
        if refs.empty:return self._finish([])
        symbols=refs["Symbol"].astype(str).str.upper().drop_duplicates().tolist(); self.diagnostics["stocks_scanned"]=len(symbols); data=self._market_snapshot(symbols); self.universe_market_data=data
        available=sum(1 for s in symbols if s in data and not data[s].empty); self.diagnostics["market_data_coverage"]=available/len(symbols) if symbols else 0.0
        if available<math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE): self.diagnostics["rejections"]["missing_data"]+=len(symbols)-available; self._write_diagnostics(); return self._finish([])
        change=self._nifty_snapshot()
        if change is None:return self._finish([])
        self.diagnostics["nifty500_change_pct"]=round(change,4); self.diagnostics["nifty500_direction"]="BULLISH" if change>=NIFTY500_MIN_CHANGE_PCT else "BEARISH" if change<=-NIFTY500_MIN_CHANGE_PCT else "NEUTRAL"; self.diagnostics["nifty500_bullish"]=int(change>=NIFTY500_MIN_CHANGE_PCT); self.diagnostics["nifty500_bearish"]=int(change<=-NIFTY500_MIN_CHANGE_PCT); self.diagnostics["nifty500_neutral"]=int(abs(change)<NIFTY500_MIN_CHANGE_PCT)
        self._build_gap_board(refs,data); self._seed_and_update("BUY",change,data); self._seed_and_update("SELL",change,data); signals=self._final_signals(change,data)
        self.diagnostics["market_alignment_passed"]=len(self.qualified["BUY"])+len(self.qualified["SELL"]); self.diagnostics["strategy_setup_passed"]=len(signals); self.diagnostics["final_signals"]=len(signals); self._save_waiting(); self._write_diagnostics(); return signals
    def _finish(self,signals): self.diagnostics["final_signals"]=len(signals); self._write_diagnostics(); return signals
