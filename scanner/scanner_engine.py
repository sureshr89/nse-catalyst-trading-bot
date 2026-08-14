"""NIFTY 500 scanner for the PDH/PDL + today's Open reversal strategy."""
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
from config.settings import REQUIRE_MARKET_ALIGNMENT, REQUIRE_STOCK_ALIGNMENT, TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from strategy.open_reversal_engine import OpenReversalEngine


class ScannerEngine:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = OpenReversalEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame(); self.opening_candidates = pd.DataFrame(); self.gap_analysis = pd.DataFrame()
        self.universe_market_data = {}; self.nifty500_market_data = pd.DataFrame(); self._prepared_date = None; self._opening_prepared_date = None
        self.diagnostics = self._empty_diagnostics()

    @staticmethod
    def _empty_diagnostics():
        return {"timestamp": None,"stocks_scanned":0,"liquidity_passed":0,"opening_setup_passed":0,"market_alignment_passed":0,"strategy_setup_passed":0,"stock_alignment_passed":0,"final_signals":0,"gap_up_count":0,"gap_down_count":0,"gap_data_count":0,"nifty500_direction":"UNKNOWN","nifty500_bullish":0,"nifty500_bearish":0,"nifty500_neutral":0,"nifty500_coverage":0,"rejections":{"missing_data":0,"liquidity":0,"opening_setup":0,"market_alignment":0,"pdh_pdl_not_reached":0,"no_open_cross":0,"strategy_setup":0,"stock_alignment":0}}

    @staticmethod
    def _today():
        return pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")

    def _write_diagnostics(self):
        payload=dict(self.diagnostics); payload["rejections"]=dict(self.diagnostics.get("rejections",{})); payload["timestamp"]=datetime.now().astimezone().isoformat(timespec="seconds"); self.diagnostics["timestamp"]=payload["timestamp"]
        path=Path(__file__).resolve().parents[1]/"outputs"/"scanner_diagnostics.json"; path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_name("scanner_diagnostics.tmp")
        try: temp.write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8"); temp.replace(path)
        except Exception as error: print("Could not write diagnostics:",error)

    def _write_gap_analysis(self, rows):
        path=Path(__file__).resolve().parents[1]/"outputs"/"gap_analysis.csv"; path.parent.mkdir(parents=True,exist_ok=True)
        try: pd.DataFrame(rows).to_csv(path,index=False)
        except Exception as error: print("Could not write gap analysis:",error)

    def _finish(self, signals=None):
        result=signals or []; self.diagnostics["final_signals"]=len(result); self._write_diagnostics(); return result

    def prepare_reference_data(self, force=False):
        today=self._today()
        if not force and self._prepared_date==today and not self.references.empty: return self.references
        self.universe=self.universe_engine.get_dataframe(refresh=True); self.references=ReferenceStore(self.universe).prepare(); self._prepared_date=today
        return self.references

    def prepare_opening_candidates(self, force=False):
        today=self._today()
        if not force and self._opening_prepared_date==today and not self.opening_candidates.empty: return self.opening_candidates
        references=self.prepare_reference_data(force=force)
        if references.empty:
            self.diagnostics["rejections"]["missing_data"]=len(self.universe); self._write_diagnostics(); return pd.DataFrame()
        refs=references.copy()
        for c in ["PreviousDayClose","PreviousDayTurnover","PDH","PDL"]: refs[c]=pd.to_numeric(refs[c],errors="coerce")
        total=len(refs); refs=refs.dropna(subset=["PDH","PDL","PreviousDayClose","PreviousDayTurnover"]); self.diagnostics["stocks_scanned"]=len(self.universe); self.diagnostics["rejections"]["missing_data"]=max(0,total-len(refs))
        if refs.empty: self._write_diagnostics(); return pd.DataFrame()
        cutoff=float(refs["PreviousDayTurnover"].median()); refs["LiquidityQualified"]=refs["PreviousDayTurnover"]>=cutoff; self.diagnostics["liquidity_passed"]=int(refs["LiquidityQualified"].sum()); self.diagnostics["rejections"]["liquidity"]=int((~refs["LiquidityQualified"]).sum())
        symbols=refs["Symbol"].astype(str).str.upper().tolist(); market_data=self.price_data.get_multi_1m(symbols); self.universe_market_data=market_data; rows=[]; gap_rows=[]
        for _,ref in refs.iterrows():
            symbol=str(ref["Symbol"]).upper(); candles=market_data.get(symbol)
            if candles is None or candles.empty: self.diagnostics["rejections"]["missing_data"]+=1; continue
            today_data=self.price_data.today_only(candles)
            if today_data.empty: self.diagnostics["rejections"]["missing_data"]+=1; continue
            try: today_open=float(today_data.iloc[0]["Open"]); pdc=float(ref["PreviousDayClose"]); pdh=float(ref["PDH"]); pdl=float(ref["PDL"])
            except (TypeError,ValueError): self.diagnostics["rejections"]["missing_data"]+=1; continue
            if today_open>pdh: gap_type="GAP_UP_PDH"; setup="BUY_PDH_TO_OPEN"; gap_value=today_open-pdh; gap_percent=(gap_value/pdh*100) if pdh else 0
            elif today_open<pdl: gap_type="GAP_DOWN_PDL"; setup="SELL_PDL_TO_OPEN"; gap_value=today_open-pdl; gap_percent=(gap_value/pdl*100) if pdl else 0
            else: gap_type="INSIDE_PDH_PDL"; setup="NO_GAP_SETUP"; gap_value=0; gap_percent=0
            gap_from_close=today_open-pdc; gap_pct_close=(gap_from_close/pdc*100) if pdc else 0
            gap_rows.append({"Symbol":symbol,"PreviousClose":round(pdc,4),"TodayOpen":round(today_open,4),"Gap":round(gap_value,4),"GapPercent":round(gap_percent,3),"GapType":gap_type,"PDH":round(pdh,4),"PDL":round(pdl,4),"GapFromPreviousClose":round(gap_from_close,4),"GapPercentFromPreviousClose":round(gap_pct_close,3),"PreviousDayTurnover":round(float(ref["PreviousDayTurnover"]),2),"LiquidityQualified":bool(ref["LiquidityQualified"]),"PreparedAtIST":datetime.now().astimezone().isoformat(timespec="seconds")})
            if not bool(ref["LiquidityQualified"]): continue
            if setup=="NO_GAP_SETUP": self.diagnostics["rejections"]["opening_setup"]+=1; continue
            rows.append({"Symbol":symbol,"PDH":round(pdh,4),"PDL":round(pdl,4),"TodayOpen":round(today_open,4),"PreviousDayClose":round(pdc,4),"Gap":round(gap_value,4),"GapPercent":round(gap_percent,3),"GapType":gap_type,"OpeningSetup":setup,"GapFromPreviousClose":round(gap_from_close,4),"GapPercentFromPreviousClose":round(gap_pct_close,3),"PreviousDayTurnover":round(float(ref["PreviousDayTurnover"]),2),"LiquidityQualified":True})
        self.gap_analysis=pd.DataFrame(gap_rows); self.diagnostics["gap_data_count"]=len(gap_rows); self.diagnostics["gap_up_count"]=sum(r["GapType"]=="GAP_UP_PDH" for r in gap_rows); self.diagnostics["gap_down_count"]=sum(r["GapType"]=="GAP_DOWN_PDL" for r in gap_rows); self._write_gap_analysis(gap_rows)
        result=pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame(); self.diagnostics["opening_setup_passed"]=len(result); self.opening_candidates=result; self._opening_prepared_date=today; self._write_diagnostics(); return result

    @staticmethod
    def _direction(df):
        if df is None or df.empty: return "UNKNOWN"
        opening=float(df.iloc[0]["Open"]); close=float(df.iloc[-1]["Close"]); return "BULLISH" if close>opening else "BEARISH" if close<opening else "NEUTRAL"

    def _nifty500_candle(self, as_of):
        data=self.price_data.today_only(self.price_data.get_index_1m("^CRSLDX"))
        if data.empty: return None
        stamp=pd.Timestamp(as_of)
        if stamp.tzinfo is None: stamp=stamp.tz_localize("Asia/Kolkata")
        else: stamp=stamp.tz_convert("Asia/Kolkata")
        completed=data[data["Datetime"]<=stamp]
        return None if completed.empty else completed.iloc[-1].to_dict()

    def scan(self):
        candidates=self.prepare_opening_candidates()
        if candidates.empty: return self._finish([])
        signals=[]
        for _,row in candidates.iterrows():
            symbol=str(row["Symbol"]).upper(); candles=self.universe_market_data.get(symbol)
            if candles is None or candles.empty: continue
            trigger_probe=self.strategy.build(symbol,candles,row["PDH"],row["PDL"],row["TodayOpen"],"UNKNOWN",None)
            if trigger_probe is None: continue
            trigger_time=trigger_probe.get("entry_time"); nifty_candle=self._nifty500_candle(trigger_time)
            nifty_dir=self.strategy._candle_direction(nifty_candle); side=trigger_probe["signal"]; required="BULLISH" if side=="BUY" else "BEARISH"
            self.diagnostics["nifty500_direction"]=nifty_dir
            if REQUIRE_MARKET_ALIGNMENT and nifty_dir!=required:
                self.diagnostics["rejections"]["market_alignment"]+=1; continue
            self.diagnostics["market_alignment_passed"]+=1
            trigger_rows=candles[candles["Datetime"]==pd.Timestamp(trigger_time)]
            stock_dir=self.strategy._candle_direction(trigger_rows)
            if REQUIRE_STOCK_ALIGNMENT and stock_dir!=required:
                self.diagnostics["rejections"]["stock_alignment"]+=1; continue
            self.diagnostics["stock_alignment_passed"]+=1
            signal=self.strategy.build(symbol,candles,row["PDH"],row["PDL"],row["TodayOpen"],nifty_dir,nifty_candle)
            if signal is not None:
                signal.update({"nifty500_universe":True,"liquidity_qualified":True,"gap":row.get("Gap"),"gap_percent":row.get("GapPercent"),"gap_type":row.get("GapType")})
                signals.append(signal); self.diagnostics["strategy_setup_passed"]+=1
        return self._finish(signals)
