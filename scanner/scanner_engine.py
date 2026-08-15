"""NIFTY 500 scanner for the direct 1-minute PDH/PDL + Today's Open strategy."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json, math
import pandas as pd
from config.settings import REQUIRE_MARKET_ALIGNMENT, TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO, HIGH_LIQUIDITY_PERCENTILE, NIFTY500_MIN_CHANGE_PCT
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from strategy.open_reversal_engine import OpenReversalEngine
INDIA_TZ=ZoneInfo("Asia/Kolkata")
MIN_MARKET_DATA_COVERAGE=0.95
class ScannerEngine:
    """Use current completed 1-minute prices; no candle-pattern or stock-direction filters."""
    def __init__(self):
        self.universe_engine=StockUniverse();self.universe=self.universe_engine.get_dataframe(refresh=False);self.price_data=PriceData();self.strategy=OpenReversalEngine(TRADING_START,LAST_ENTRY_TIME,RISK_REWARD_RATIO);self.references=pd.DataFrame();self.opening_candidates=pd.DataFrame();self.gap_analysis=pd.DataFrame();self.universe_market_data={};self.nifty500_market_data=pd.DataFrame();self._prepared_date=None;self.diagnostics=self._empty_diagnostics()
    @staticmethod
    def _empty_diagnostics():
        return {"timestamp":None,"stocks_scanned":0,"liquidity_passed":0,"opening_setup_passed":0,"market_alignment_passed":0,"strategy_setup_passed":0,"stock_alignment_passed":0,"final_signals":0,"gap_up_count":0,"gap_down_count":0,"gap_data_count":0,"nifty500_direction":"UNKNOWN","nifty500_change_pct":0.0,"nifty500_bullish":0,"nifty500_bearish":0,"nifty500_neutral":0,"nifty500_coverage":0,"market_data_coverage":0.0,"rejections":{"missing_data":0,"liquidity":0,"opening_setup":0,"market_alignment":0,"pdh_pdl_not_reached":0,"no_open_cross":0,"strategy_setup":0,"stock_alignment":0}}
    @staticmethod
    def _today():return pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d")
    @staticmethod
    def _ist_series(values):
        stamps=pd.to_datetime(values,errors="coerce")
        try:return stamps.dt.tz_localize(INDIA_TZ) if stamps.dt.tz is None else stamps.dt.tz_convert(INDIA_TZ)
        except Exception:return stamps
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
    def _build_candidates(self,references,market_data):
        refs=references.copy()
        for col in ["PreviousDayClose","PreviousDayTurnover","PDH","PDL"]:refs[col]=pd.to_numeric(refs[col],errors="coerce")
        refs=refs.dropna(subset=["PDH","PDL","PreviousDayClose","PreviousDayTurnover"])
        percentile=max(0.0,min(1.0,float(HIGH_LIQUIDITY_PERCENTILE)));cutoff=float(refs["PreviousDayTurnover"].quantile(percentile)) if not refs.empty else 0.0;refs["LiquidityQualified"]=refs["PreviousDayTurnover"]>=cutoff
        self.diagnostics["liquidity_passed"]=int(refs["LiquidityQualified"].sum());self.diagnostics["rejections"]["liquidity"]=int((~refs["LiquidityQualified"]).sum())
        rows=[];gaps=[]
        for _,ref in refs.iterrows():
            symbol=str(ref["Symbol"]).upper();data=market_data.get(symbol)
            if data is None or data.empty:continue
            today=self.price_data.today_only(data)
            if today.empty:continue
            try:today_open=float(today.iloc[0]["Open"]);pdc=float(ref["PreviousDayClose"]);pdh=float(ref["PDH"]);pdl=float(ref["PDL"])
            except (TypeError,ValueError):continue
            if today_open>pdh:gap_type,setup="GAP_UP","GAP_UP_ABOVE_PDH"
            elif today_open<pdl:gap_type,setup="GAP_DOWN","GAP_DOWN_BELOW_PDL"
            else:gap_type,setup="INSIDE_PDH_PDL","NO_GAP_SETUP"
            gap_from_close=today_open-pdc;gap_pct=(gap_from_close/pdc*100) if pdc else 0.0
            gaps.append({"Symbol":symbol,"PreviousClose":round(pdc,4),"TodayOpen":round(today_open,4),"Gap":round(gap_from_close,4),"GapPercent":round(gap_pct,3),"GapType":gap_type,"PDH":round(pdh,4),"PDL":round(pdl,4),"PreviousDayTurnover":round(float(ref["PreviousDayTurnover"]),2),"LiquidityQualified":bool(ref["LiquidityQualified"]),"PreparedAtIST":datetime.now(INDIA_TZ).isoformat(timespec="seconds")})
            if setup=="NO_GAP_SETUP":self.diagnostics["rejections"]["opening_setup"]+=1;continue
            rows.append({"Symbol":symbol,"PDH":pdh,"PDL":pdl,"TodayOpen":today_open,"PreviousDayClose":pdc,"Gap":gap_from_close,"GapPercent":gap_pct,"GapType":gap_type,"OpeningSetup":setup,"PreviousDayTurnover":float(ref["PreviousDayTurnover"]),"LiquidityQualified":bool(ref["LiquidityQualified"])})
        self.gap_analysis=pd.DataFrame(gaps);self.diagnostics["gap_data_count"]=len(gaps);self.diagnostics["gap_up_count"]=sum(x["GapType"]=="GAP_UP" for x in gaps);self.diagnostics["gap_down_count"]=sum(x["GapType"]=="GAP_DOWN" for x in gaps);self._write_gap_analysis(gaps);result=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame();self.opening_candidates=result;self.diagnostics["opening_setup_passed"]=len(result);return result
    def prepare_opening_candidates(self,force=False):
        """Compatibility/pre-market helper: prepare today's gap candidates using fresh 1m prices."""
        references=self.prepare_reference_data(force=force)
        if references.empty:return pd.DataFrame()
        symbols=references["Symbol"].astype(str).str.upper().drop_duplicates().tolist();market_data=self.price_data.get_multi_1m(symbols);self.universe_market_data=market_data
        available=sum(1 for s in symbols if s in market_data and not market_data[s].empty);required=math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE)
        if available<required:
            self.diagnostics["rejections"]["missing_data"]+=len(symbols)-available;self._write_diagnostics();return pd.DataFrame()
        return self._build_candidates(references,market_data)
    def _aligned_coverage(self,symbols,market_data,expected):
        aligned=0
        for symbol in symbols:
            data=market_data.get(symbol)
            if data is None or data.empty:continue
            if bool((self._ist_series(data["Datetime"])==expected).any()):aligned+=1
        return aligned
    def scan(self):
        self.diagnostics=self._empty_diagnostics();references=self.prepare_reference_data()
        if references.empty:return self._finish([])
        symbols=references["Symbol"].astype(str).str.upper().drop_duplicates().tolist();self.diagnostics["stocks_scanned"]=len(symbols);market_data=self.price_data.get_multi_1m(symbols);self.universe_market_data=market_data
        available=sum(1 for s in symbols if s in market_data and not market_data[s].empty);coverage=available/len(symbols) if symbols else 0.0;self.diagnostics["market_data_coverage"]=coverage;required=math.ceil(len(symbols)*MIN_MARKET_DATA_COVERAGE)
        if available<required:self.diagnostics["rejections"]["missing_data"]+=len(symbols)-available;self._write_diagnostics();return self._finish([])
        expected=self._latest_completed_minute();aligned=self._aligned_coverage(symbols,market_data,expected);aligned_cov=aligned/len(symbols) if symbols else 0.0;self.diagnostics["market_data_coverage"]=aligned_cov
        if aligned<required:self.diagnostics["rejections"]["missing_data"]+=len(symbols)-aligned;self._write_diagnostics();return self._finish([])
        self.nifty500_market_data=self.price_data.get_index_1m("^CRSLDX");self.diagnostics["nifty500_coverage"]=int(not self.nifty500_market_data.empty)
        if self.nifty500_market_data.empty:self.diagnostics["rejections"]["market_alignment"]+=1;return self._finish([])
        if REQUIRE_MARKET_ALIGNMENT and not bool((self._ist_series(self.nifty500_market_data["Datetime"])==expected).any()):self.diagnostics["rejections"]["market_alignment"]+=1;self._write_diagnostics();return self._finish([])
        nifty_change=self.price_data.get_index_change_pct("^CRSLDX")
        if nifty_change is None:return self._finish([])
        nifty_change=float(nifty_change);self.diagnostics["nifty500_change_pct"]=round(nifty_change,4)
        if nifty_change>=NIFTY500_MIN_CHANGE_PCT:self.diagnostics["nifty500_direction"]="BULLISH";self.diagnostics["nifty500_bullish"]=1
        elif nifty_change<=-NIFTY500_MIN_CHANGE_PCT:self.diagnostics["nifty500_direction"]="BEARISH";self.diagnostics["nifty500_bearish"]=1
        else:self.diagnostics["nifty500_direction"]="NEUTRAL";self.diagnostics["nifty500_neutral"]=1
        candidates=self._build_candidates(references,market_data)
        if candidates.empty:return self._finish([])
        if REQUIRE_MARKET_ALIGNMENT and abs(nifty_change)<NIFTY500_MIN_CHANGE_PCT:self.diagnostics["rejections"]["market_alignment"]=len(candidates);self._write_diagnostics();return self._finish([])
        self.diagnostics["market_alignment_passed"]=len(candidates);signals=[]
        for _,row in candidates.iterrows():
            symbol=str(row["Symbol"]).upper();signal=self.strategy.build(symbol,market_data.get(symbol),row["PDH"],row["PDL"],row["TodayOpen"],nifty_change_pct=nifty_change)
            if signal is None:self.diagnostics["rejections"]["strategy_setup"]+=1;continue
            signal.update({"nifty500_universe":True,"liquidity_qualified":bool(row.get("LiquidityQualified",False)),"gap":row.get("Gap"),"gap_percent":row.get("GapPercent"),"gap_type":row.get("GapType"),"nifty500_change_pct":nifty_change});signals.append(signal);self.diagnostics["strategy_setup_passed"]+=1
        return self._finish(signals)
