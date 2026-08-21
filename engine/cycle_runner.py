"""Production cycle orchestration for the clean Dhan -> S1-S5 -> paper path."""
from datetime import time
from pathlib import Path
import pandas as pd
from config.settings import TRADING_START,LAST_ENTRY_TIME,SQUARE_OFF_TIME,DAILY_MAX_LOSS_PER_STRATEGY,MAX_TRADES_PER_STRATEGY_PER_DAY
OUTPUT=Path("outputs");SIGNAL_FILE=OUTPUT/"signals.csv"
def _within(now,start,end):return time.fromisoformat(start)<=now.time()<=time.fromisoformat(end)
def _candidate(quote,ref,side):
 try:op=float(quote.get("TodayOpen"));hi=float(quote.get("TodayHigh"));lo=float(quote.get("TodayLow"));ltp=float(quote.get("LTP"));pdh=float(ref.get("PDH"));pdl=float(ref.get("PDL"))
 except (TypeError,ValueError):return False
 if side=="BUY":return ltp>op and (op>pdh or (pdl<op<pdh and lo<=pdl) or ltp>pdh)
 if side=="SELL":return ltp<op and (op<pdl or (pdl<op<pdh and hi>=pdh) or ltp<pdl)
 return False
def run_cycle(engine):
 """Run one safe Dhan market-data/strategy/paper-execution cycle."""
 now=engine.now()
 if not _within(now,"09:15","15:30"):return []
 snap=engine._market_snapshot()
 # Live quotes can be displayed even when the trade gate is not ready. Never trade until every gate is verified.
 if not snap.get("trade_ready"):return []
 for symbol,position in list(engine.paper_engine.open_positions.items()):
  quote=snap.get("dhan_quotes",{}).get(symbol,{})
  if quote:engine.paper_engine.process_live_price(symbol,quote.get("LTP"),timestamp=now,high=quote.get("TodayHigh"),low=quote.get("TodayLow"))
 if now.time()>=time.fromisoformat(SQUARE_OFF_TIME):
  for symbol in list(engine.paper_engine.open_positions):
   ltp=snap.get("dhan_quotes",{}).get(symbol,{}).get("LTP")
   if ltp:engine.paper_engine.close_position(symbol,ltp,now,"FORCE_SQUARE_OFF_15:00")
  return []
 if not _within(now,TRADING_START,LAST_ENTRY_TIME):return []
 side="BUY" if snap.get("buy_alignment") else "SELL" if snap.get("sell_alignment") else None
 if side is None:return []
 signals=[]
 for _,ref in engine.references.iterrows():
  symbol=str(ref.get("Symbol","")).upper().strip()
  if not symbol or engine.paper_engine.has_open_position(symbol):continue
  quote=snap.get("dhan_quotes",{}).get(symbol,{})
  if not quote or not _candidate(quote,ref,side):continue
  try:intraday=engine.price_data.get_1m(symbol)
  except Exception:intraday=pd.DataFrame()
  if intraday is None or intraday.empty:continue
  local_snap=dict(snap);local_snap["intraday"]={symbol:intraday};stock_signals=engine._evaluate_stock(symbol,ref,local_snap)
  for signal in stock_signals:
   strategy=str(signal.get("strategy","")).upper()
   if strategy not in engine.daily_counts or engine.daily_counts[strategy]>=MAX_TRADES_PER_STRATEGY_PER_DAY or engine.daily_pnl_by_strategy.get(strategy,0.0)<=-float(DAILY_MAX_LOSS_PER_STRATEGY):continue
   trade=dict(signal);trade.update({"approved":True,"entry_time":now});opened=engine.paper_engine.open_trade(trade)
   if opened.get("opened"):
    engine.daily_counts[strategy]+=1;signal["trade_id"]=opened.get("trade_id");signals.append(signal);break
 engine.last_signals=signals;engine.diagnostics["final_signals"]=len(signals);engine.diagnostics["signals_by_strategy"]={s:sum(1 for x in signals if str(x.get("strategy","")).upper()==s) for s in engine.daily_counts};engine.diagnostics["trade_path_status"]="READY" if signals or snap.get("buy_alignment") or snap.get("sell_alignment") else "BLOCKED";engine._write_diagnostics()
 if signals:OUTPUT.mkdir(parents=True,exist_ok=True);pd.DataFrame(signals).to_csv(SIGNAL_FILE,index=False)
 return signals
