"""Clean S1-S5 NIFTY 500 paper-trading strategy contract.

No broker, Yahoo, dashboard, or legacy strategy code belongs here. The engine
supplies a verified Dhan market snapshot and completed 1-minute candles.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict
import math
RR = 1.25
MIN_RISK = 1400.0
MAX_RISK = 1500.0
CAPITAL_PER_TRADE = 250000.0
MIN_MARKET_COVERAGE = 475
@dataclass(frozen=True)
class TradeSignal:
    strategy: str; side: str; symbol: str; entry: float; stop_loss: float; target: float
    risk_per_share: float; quantity: int; actual_risk: float; capital_used: float; rr: float
    nifty500_change_pct: float; sector_alignment_pct: float; ad_ratio: float
    previous_candle_open: float; previous_candle_close: float; previous_candle_color: str
    entry_reason: str; exit_rules: str
    def to_dict(self) -> Dict[str, Any]:
        data=asdict(self); data.update({"signal":data["side"],"setup_type":data["strategy"],"reason":data["entry_reason"]}); return data
def _finite_positive(v):
    try:x=float(v); return math.isfinite(x) and x>0
    except (TypeError,ValueError):return False
def market_gate(side,nifty500_change_pct,sector_alignment_pct,ad_ratio,ad_coverage=MIN_MARKET_COVERAGE,positive_sectors=0,negative_sectors=0):
    try: change,sector,ad=map(float,(nifty500_change_pct,sector_alignment_pct,ad_ratio)); coverage=int(ad_coverage); pos=int(positive_sectors); neg=int(negative_sectors)
    except (TypeError,ValueError):return False
    if coverage < MIN_MARKET_COVERAGE or not all(math.isfinite(x) for x in (change,sector,ad)):return False
    if side=="BUY":return change>0 and ad>1 and pos>neg
    if side=="SELL":return change<0 and ad<1 and neg>pos
    return False
def position_size(entry,stop_loss):
    try:entry,stop_loss=float(entry),float(stop_loss)
    except (TypeError,ValueError):return None
    if not _finite_positive(entry) or not _finite_positive(stop_loss):return None
    rps=abs(entry-stop_loss)
    if not _finite_positive(rps):return None
    max_qty=int(CAPITAL_PER_TRADE//entry); min_qty=max(1,math.ceil((MIN_RISK-1e-12)/rps)); max_risk_qty=min(max_qty,math.floor(MAX_RISK/rps))
    if min_qty>max_risk_qty:return None
    qty=min_qty; risk=qty*rps; capital=qty*entry
    if not(MIN_RISK<=risk<=MAX_RISK and capital<=CAPITAL_PER_TRADE):return None
    return qty,rps,risk,capital
def make_signal(strategy,side,symbol,entry,stop_loss,nifty500_change_pct,sector_alignment_pct,ad_ratio,ad_coverage,reason,previous_candle_open,previous_candle_close,positive_sectors=0,negative_sectors=0):
    canonical=str(strategy).upper().strip()
    if canonical not in {"S1","S2","S3","S4","S5"}:return None
    if not market_gate(side,nifty500_change_pct,sector_alignment_pct,ad_ratio,ad_coverage,positive_sectors,negative_sectors):return None
    try:entry,stop_loss,po,pc=map(float,(entry,stop_loss,previous_candle_open,previous_candle_close))
    except (TypeError,ValueError):return None
    if not all(_finite_positive(x) for x in (entry,stop_loss,po,pc)):return None
    if side=="BUY":
        if stop_loss>=entry:return None
        target=entry+(entry-stop_loss)*RR
    elif side=="SELL":
        if stop_loss<=entry:return None
        target=entry-(stop_loss-entry)*RR
    else:return None
    sizing=position_size(entry,stop_loss)
    if sizing is None:return None
    qty,rps,risk,capital=sizing; color="GREEN" if pc>po else "RED" if pc<po else "FLAT"
    return TradeSignal(canonical,str(side).upper(),str(symbol).upper(),round(entry,4),round(stop_loss,4),round(target,4),round(rps,4),qty,round(risk,2),round(capital,2),RR,round(float(nifty500_change_pct),4),round(float(sector_alignment_pct),4),round(float(ad_ratio),4),round(po,4),round(pc,4),color,reason,"Exit at SL or 1.25R target; force square-off at 15:00 IST")
def _c(g):
    g=dict(g); po=g.pop("previous_candle_open",None); pc=g.pop("previous_candle_close",None)
    allowed={"nifty500_change_pct","sector_alignment_pct","ad_ratio","ad_coverage","positive_sectors","negative_sectors"}
    return {k:v for k,v in g.items() if k in allowed},po,pc
def evaluate_s1(symbol,side,today_open,pdh,pdl,today_low,today_high,ltp,**g):
    g,po,pc=_c(g)
    if po is None or pc is None:return None
    try:today_open,pdh,pdl,today_low,today_high,ltp=map(float,(today_open,pdh,pdl,today_low,today_high,ltp))
    except (TypeError,ValueError):return None
    if side=="BUY" and today_open>pdh and today_low<=pdh and ltp>today_open:return make_signal("S1",side,symbol,ltp,pdh,previous_candle_open=po,previous_candle_close=pc,reason="Open > PDH -> PDH swept/touched -> live LTP reclaimed above open",**g)
    if side=="SELL" and today_open<pdl and today_high>=pdl and ltp<today_open:return make_signal("S1",side,symbol,ltp,pdl,previous_candle_open=po,previous_candle_close=pc,reason="Open < PDL -> PDL swept/touched -> live LTP reclaimed below open",**g)
    return None
def evaluate_s2(symbol,side,pdh,pdl,pullback_low,pullback_high,ltp,breakout_seen=False,**g):
    g,po,pc=_c(g)
    if po is None or pc is None:return None
    try:pdh,pdl,ltp=float(pdh),float(pdl),float(ltp); pullback_low=None if pullback_low is None else float(pullback_low); pullback_high=None if pullback_high is None else float(pullback_high)
    except (TypeError,ValueError):return None
    if side=="BUY" and breakout_seen and ltp>=pdh and pullback_low is not None and pullback_low<=pdh:return make_signal("S2",side,symbol,ltp,pullback_low,previous_candle_open=po,previous_candle_close=pc,reason="Break PDH -> retest PDH -> live reclaim",**g)
    if side=="SELL" and breakout_seen and ltp<=pdl and pullback_high is not None and pullback_high>=pdl:return make_signal("S2",side,symbol,ltp,pullback_high,previous_candle_open=po,previous_candle_close=pc,reason="Break PDL -> retest PDL -> live failure",**g)
    return None
def evaluate_s3(symbol,side,today_open,pdh,pdl,today_low,today_high,ltp,**g):
    g,po,pc=_c(g)
    if po is None or pc is None:return None
    try:today_open,pdh,pdl,today_low,today_high,ltp=map(float,(today_open,pdh,pdl,today_low,today_high,ltp))
    except (TypeError,ValueError):return None
    inside=pdl<today_open<pdh
    if side=="BUY" and inside and today_low<=pdl and ltp>today_open:return make_signal("S3",side,symbol,ltp,today_low,previous_candle_open=po,previous_candle_close=pc,reason="Open inside range -> sweep below PDL -> live reversal above open",**g)
    if side=="SELL" and inside and today_high>=pdh and ltp<today_open:return make_signal("S3",side,symbol,ltp,today_high,previous_candle_open=po,previous_candle_close=pc,reason="Open inside range -> sweep above PDH -> live reversal below open",**g)
    return None
def evaluate_s4(symbol,side,today_high,today_low,prior_intraday_high,prior_intraday_low,ltp,**g):
    g,po,pc=_c(g)
    if po is None or pc is None:return None
    try:today_high,today_low,ltp=float(today_high),float(today_low),float(ltp); prior_intraday_high=None if prior_intraday_high is None else float(prior_intraday_high); prior_intraday_low=None if prior_intraday_low is None else float(prior_intraday_low)
    except (TypeError,ValueError):return None
    if side=="BUY" and prior_intraday_high is not None and ltp>prior_intraday_high:return make_signal("S4",side,symbol,ltp,prior_intraday_low if prior_intraday_low else today_low,previous_candle_open=po,previous_candle_close=pc,reason="Live LTP broke previously formed intraday high",**g)
    if side=="SELL" and prior_intraday_low is not None and ltp<prior_intraday_low:return make_signal("S4",side,symbol,ltp,prior_intraday_high if prior_intraday_high else today_high,previous_candle_open=po,previous_candle_close=pc,reason="Live LTP broke previously formed intraday low",**g)
    return None
def evaluate_s5(symbol,side,pdh,pdl,ltp,**g):
    g,po,pc=_c(g)
    if po is None or pc is None:return None
    try:pdh,pdl,ltp=map(float,(pdh,pdl,ltp))
    except (TypeError,ValueError):return None
    if side=="BUY" and ltp>pdh:return make_signal("S5",side,symbol,ltp,pdh,previous_candle_open=po,previous_candle_close=pc,reason="Live LTP broke above PDH",**g)
    if side=="SELL" and ltp<pdl:return make_signal("S5",side,symbol,ltp,pdl,previous_candle_open=po,previous_candle_close=pc,reason="Live LTP broke below PDL",**g)
    return None
STRATEGY_DEFINITIONS={"S1":{"name":"PDH/PDL Sweep + Open Reclaim","entry":"Open beyond PDH/PDL -> touch/sweep -> live reclaim of open","sl":"PDH / PDL","target":"1.25R"},"S2":{"name":"PDH/PDL Breakout + Retest","entry":"Break PDH/PDL -> retest -> live reclaim/fail","sl":"Retest Low / High","target":"1.25R"},"S3":{"name":"Opposite PDH/PDL Sweep + Open Reversal","entry":"Open inside PDH/PDL -> opposite sweep -> live reversal through open","sl":"Today's Low / High","target":"1.25R"},"S4":{"name":"Intraday High/Low Breakout","entry":"Break previously completed intraday high/low","sl":"Previous intraday Low / High","target":"1.25R"},"S5":{"name":"Direct PDH/PDL Breakout","entry":"Break PDH/PDL","sl":"PDH / PDL","target":"1.25R"}}
def evaluate(strategy,**kwargs):
    fn={"S1":evaluate_s1,"S2":evaluate_s2,"S3":evaluate_s3,"S4":evaluate_s4,"S5":evaluate_s5}.get(str(strategy).upper().strip())
    if fn is None:raise ValueError(f"Unknown price-action strategy: {strategy}")
    return fn(**kwargs)