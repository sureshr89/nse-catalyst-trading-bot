"""NIFTY 500 live 1-minute price scanner for the PDH/PDL + Today's Open strategy."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import pandas as pd
from config.settings import REQUIRE_MARKET_ALIGNMENT, TRADING_START, LAST_ENTRY_TIME, HIGH_LIQUIDITY_PERCENTILE
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from strategy.open_reversal_engine import OpenReversalEngine

INDIA_TZ=ZoneInfo("Asia/Kolkata")
MIN_MARKET_DATA_COVERAGE=0.95
NIFTY_MIN_CHANGE_PCT=0.25

class ScannerEngine:
    """Scan live 1-minute prices; no candlestick-pattern confirmation is used."""
    def __init__(self):
        self.universe_engine=StockUniverse();self.universe=self.universe_engine.get_dataframe(refresh=False);self.price_data=PriceData();self.strategy=OpenReversalEngine(TRADING_START,LAST_ENTRY_TIME,1.25);self.references=pd.DataFrame();self.opening_candidates=pd.DataFrame();self.gap_analysis=pd.DataFrame();self.universe_market_data={};self.nifty500_market_data=pd.DataFrame();self._prepared_date=None;self._opening_prepared_date=None;self.diagnostics=self._empty_diagnostics()
    @staticmethod
    def _empty_diagnostics():
        return {"timestamp":None,"stocks_scanned":0,"liquidity_passed":0,"opening_setup_passed":0,"market_alignment_passed":0,"strategy_setup_passed":0,"stock_alignment_passed":0,"final_signals":0,"gap_up_count":0,"gap_down_count":0,"gap_data_count":0,"nifty500_direction":"UNKNOWN","nifty500_change_pct":0.0,"nifty500_bullish":0,"nifty500_bearish":0,"nifty500_neutral":0,"nifty500_coverage":0,"market_data_coverage":0.0,"rejections":{"missing_data":0,"liquidity":0,"opening_setup":0,"market_alignment":0,"pdh_pdl_not_reached":0,"no_open_cross":0,"strategy_setup":0,"stock_alignment":0}}
    @staticmethod
    def _today():return pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d")
    @staticmethod
    def _ist_timestamp(value):
        stamp=pd.Timestamp(value);return stamp.tz_localize(INDIA_TZ) if stamp.tzinfo is None else stamp.tz_convert(INDIA_TZ)
    @staticmethod
    def _latest_completed_minute():return datetime.now(INDIA_TZ).replace(second=0,microsecond=0)-pd.Timedelta(minutes=1)
    def _write_diagnostics(self):
        payload=dict(self.diagnostics);payload["rejections"]=dict(self.diagnostics.get("rejections",{}));payload["timestamp"]=datetime.now(INDIA_TZ).isoformat(timespec="seconds");self.diagnostics["timestamp"]=payload["timestamp"];path=Path(__file__).resolve().parents[1]/"outputs"/"scanner_diagnostics.json";path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name("scanner_diagnostics.tmp")
        try:temp.write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8");temp.replace(path)
        except Exception as error:print("Could not write diagnostics:",error)
    def _write_gap_analysis(self,rows):
        path=Path(__file__).resolve().parents[1]/"outputs"/"gap_analysis.csv";path.parent.mkdir(parents=True,exist_ok=True)
        try:pd.DataFrame(rows).to_csv(path,index=False)
        except Exception as error:print("Could not write gap analysis:",error)
    def _finish(self,signals=None):
        result=signals or [];self.diagnostics["final_signals"]=len(result);self._write_diagnostics();return result
    def prepare_reference_data(self,force=False):
        today=self._today()
        if not force and self._prepared_date==today and not self.references.empty:return self.references
        self.universe=self.universe_engine.get_dataframe(refresh=True);references=ReferenceStore(self.universe).prepare()
        if references is None or references.empty:self.references=pd.DataFrame();self._prepared_date=None;return self.references
        self.references=references;self._prepared_date=today;return self.references
    def prepare_opening_candidates(self,force=False):
        today=self._today()
        if not force and self._opening_prepared_date==today and not self.opening_candidates.empty:return self.opening_candidates
        references=self.prepare_reference_data(force=force)
        if references.empty:self._opening_prepared_date=None;return pd.DataFrame()
        refs=references.copy()
        for column in ["PreviousDayClose","PreviousDayTurnover","PDH","PDL"]:refs[column]=pd.to_numeric(refs[column],errors="coerce")
        total=len(refs);refs=refs.dropna(subset=["PDH","PDL","PreviousDayClose","PreviousDayTurnover"]);self.diagnostics["stocks_scanned"]=len(self.universe);self.diagnostics["rejections"]["missing_data"]=max(0,total-len(refs))
        if refs.empty:self._opening_prepared_date=None;return pd.DataFrame()
        percentile=max(0.0,min(1.0,float(HIGH_LIQUIDITY_PERCENTILE)));cutoff=float(refs["PreviousDayTurnover"].quantile(percentile));refs["LiquidityQualified"]=refs["PreviousDayTurnover"]>=cutoff;self.diagnostics["liquidity_passed"]=int(refs["LiquidityQualified"].sum());self.diagnostics["rejections"]["liquidity"]=int((~refs["LiquidityQualified"]).sum())
        symbols=refs["Symbol"].astype(str).str.upper().tolist();market_data=self.price_data.get_multi_1m(symbols);self.universe_market_data=market_data;available=sum(1 for symbol in symbols if symbol in market_data and not market_data[symbol].empty);required=math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE);coverage=available/len(symbols) if symbols else 0.0;self.diagnostics["market_data_coverage"]=coverage
        if available<required:
            self._opening_prepared_date=None;self.opening_candidates=pd.DataFrame();self.diagnostics["rejections"]["missing_data"]+=len(symbols)-available;self._write_diagnostics();print(f"NIFTY 500 current 1m coverage incomplete: {available}/{len(symbols)} ({coverage:.1%}); need at least {required}. Retrying.");return pd.DataFrame()
        rows=[];gap_rows=[]
        for _,ref in refs.iterrows():
            symbol=str(ref["Symbol"]).upper();prices=market_data.get(symbol)
            if prices is None or prices.empty:continue
            today_prices=self.price_data.today_only(prices)
            if today_prices.empty:continue
            try:today_open=float(today_prices.iloc[0]["Open"]);pdc=float(ref["PreviousDayClose"]);pdh=float(ref["PDH"]);pdl=float(ref["PDL"])
            except (TypeError,ValueError):continue
            if today_open>pdh:gap_type,setup="GAP_UP","GAP_UP_ABOVE_PDH"
            elif today_open<pdl:gap_type,setup="GAP_DOWN","GAP_DOWN_BELOW_PDL"
            else:gap_type,setup="INSIDE_PDH_PDL","NO_GAP_SETUP"
            gap_from_close=today_open-pdc;gap_pct_close=(gap_from_close/pdc*100) if pdc else 0.0
            gap_rows.append({"Symbol":symbol,"PreviousClose":round(pdc,4),"TodayOpen":round(today_open,4),"GapFromPreviousClose":round(gap_from_close,4),"GapPercentFromPreviousClose":round(gap_pct_close,3),"GapType":gap_type,"PDH":round(pdh,4),"PDL":round(pdl,4),"PreviousDayTurnover":round(float(ref["PreviousDayTurnover"]),2),"LiquidityQualified":bool(ref["LiquidityQualified"])})
            if setup=="NO_GAP_SETUP":self.diagnostics["rejections"]["opening_setup"]+=1;continue
            rows.append({"Symbol":symbol,"PDH":pdh,"PDL":pdl,"TodayOpen":today_open,"PreviousDayClose":pdc,"Gap":gap_from_close,"GapPercent":gap_pct_close,"GapType":gap_type,"OpeningSetup":setup,"PreviousDayTurnover":float(ref["PreviousDayTurnover"]),"LiquidityQualified":bool(ref["LiquidityQualified"])})
        self.gap_analysis=pd.DataFrame(gap_rows);self.diagnostics["gap_data_count"]=len(gap_rows);self.diagnostics["gap_up_count"]=sum(r["GapType"]=="GAP_UP" for r in gap_rows);self.diagnostics["gap_down_count"]=sum(r["GapType"]=="GAP_DOWN" for r in gap_rows);self._write_gap_analysis(gap_rows);result=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame();self.diagnostics["opening_setup_passed"]=len(result);self.opening_candidates=result;self._opening_prepared_date=today if len(result) else None;self._write_diagnostics();return result
    def _index_has_timestamp(self,stamp,data):
        if data is None or data.empty:return False
        try:
            timestamps=pd.to_datetime(data["Datetime"],errors="coerce");timestamps=timestamps.dt.tz_localize(INDIA_TZ) if timestamps.dt.tz is None else timestamps.dt.tz_convert(INDIA_TZ);return bool((timestamps==stamp).any())
        except Exception:return False
    def scan(self):
        self.diagnostics=self._empty_diagnostics();candidates=self.prepare_opening_candidates()
        if candidates.empty:return self._finish([])
        symbols=candidates["Symbol"].astype(str).str.upper().tolist();self.universe_market_data=self.price_data.get_multi_1m(symbols);self.nifty500_market_data=self.price_data.get_index_1m("^CRSLDX");available=sum(1 for symbol in symbols if symbol in self.universe_market_data and not self.universe_market_data[symbol].empty);required=math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE);coverage=available/len(symbols) if symbols else 0.0;self.diagnostics["market_data_coverage"]=coverage
        if available<required:self.diagnostics["rejections"]["missing_data"]+=len(symbols)-available;return self._finish([])
        expected=self._latest_completed_minute();aligned=sum(1 for symbol in symbols if symbol in self.universe_market_data and not self.universe_market_data[symbol].empty and (pd.to_datetime(self.universe_market_data[symbol]["Datetime"],errors="coerce").dt.tz_localize(INDIA_TZ) if pd.to_datetime(self.universe_market_data[symbol]["Datetime"],errors="coerce").dt.tz is None else pd.to_datetime(self.universe_market_data[symbol]["Datetime"],errors="coerce").dt.tz_convert(INDIA_TZ)).eq(expected).any());aligned_required=math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE);aligned_coverage=aligned/len(symbols) if symbols else 0.0;self.diagnostics["market_data_coverage"]=aligned_coverage
        if aligned<aligned_required:self.diagnostics["rejections"]["missing_data"]+=len(symbols)-aligned;self._write_diagnostics();print(f"Synchronized 1m coverage incomplete: {aligned}/{len(symbols)} ({aligned_coverage:.1%}) at {expected.isoformat()}; need at least {aligned_required}. Retrying.");return self._finish([])
        if REQUIRE_MARKET_ALIGNMENT and not self._index_has_timestamp(expected,self.nifty500_market_data):self.diagnostics["nifty500_coverage"]=0;self.diagnostics["rejections"]["market_alignment"]+=1;self._write_diagnostics();print(f"NIFTY 500 index data missing at {expected.isoformat()}; retrying.");return self._finish([])
        nifty_change=self.price_data.get_index_change_pct("^CRSLDX")
        if nifty_change is None:return self._finish([])
        nifty_change=float(nifty_change);self.diagnostics["nifty500_change_pct"]=round(nifty_change,4)
        if nifty_change>=NIFTY_MIN_CHANGE_PCT:self.diagnostics["nifty500_direction"]="BULLISH";self.diagnostics["nifty500_bullish"]=1
        elif nifty_change<=-NIFTY_MIN_CHANGE_PCT:self.diagnostics["nifty500_direction"]="BEARISH";self.diagnostics["nifty500_bearish"]=1
        else:self.diagnostics["nifty500_direction"]="NEUTRAL";self.diagnostics["nifty500_neutral"]=1
        signals=[]
        for _,row in candidates.iterrows():
            symbol=str(row["Symbol"]).upper();prices=self.universe_market_data.get(symbol)
            if prices is None or prices.empty:continue
            if REQUIRE_MARKET_ALIGNMENT and abs(nifty_change)<NIFTY_MIN_CHANGE_PCT:self.diagnostics["rejections"]["market_alignment"]+=1;continue
            self.diagnostics["market_alignment_passed"]+=1
            signal=self.strategy.build(symbol,prices,row["PDH"],row["PDL"],row["TodayOpen"],nifty_change_pct=nifty_change)
            if signal is None:self.diagnostics["rejections"]["strategy_setup"]+=1;continue
            signal.update({"nifty500_universe":True,"liquidity_qualified":bool(row.get("LiquidityQualified",False)),"gap":row.get("Gap"),"gap_percent":row.get("GapPercent"),"gap_type":row.get("GapType"),"nifty500_change_pct":nifty_change});signals.append(signal);self.diagnostics["strategy_setup_passed"]+=1
        return self._finish(signals)
