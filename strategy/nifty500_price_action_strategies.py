"""Five NIFTY 500 intraday OHLC/PDH/PDL price-action strategies.

Shared hard filters for S1-S5:
- Universe: full NIFTY 500.
- BUY: NIFTY 500 change > +0.25% AND full-universe A/D ratio > 1.
- SELL: NIFTY 500 change < -0.25% AND full-universe A/D ratio < 1.
- BUY requires the previous completed candle to be GREEN (Close > Open).
- SELL requires the previous completed candle to be RED (Close < Open).
- Inputs: today's OHLC/LTP, PDH/PDL and intraday running levels only.
- No sector filter and no technical indicators.
- Entries are live-LTP triggers; no current-candle-close confirmation.
- SL/target use only information available at or before entry.
- Target: 1.25R.
- Actual position risk: ₹1,400-₹1,500 inclusive; otherwise no trade.
- Mandatory square-off: 15:00 IST.
- Scanner refresh target: 10 seconds; live execution monitoring remains faster.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

RR = 1.25
MIN_RISK = 1400.0
MAX_RISK = 1500.0
MIN_NIFTY_CHANGE = 0.25
SQUARE_OFF_TIME = "15:00"
SCAN_INTERVAL_SECONDS = 10

@dataclass(frozen=True)
class TradeSignal:
    strategy: str
    side: str
    symbol: str
    entry: float
    stop_loss: float
    target: float
    risk_per_share: float
    quantity: int
    actual_risk: float
    rr: float
    nifty500_change_pct: float
    ad_ratio: float
    previous_candle_open: float
    previous_candle_close: float
    previous_candle_color: str
    entry_reason: str
    exit_rules: str
    def to_dict(self) -> Dict[str, Any]: return asdict(self)

def market_gate(side: str, nifty500_change_pct: float, ad_ratio: float) -> bool:
    try: change, ad = float(nifty500_change_pct), float(ad_ratio)
    except (TypeError, ValueError): return False
    if side == "BUY": return change > MIN_NIFTY_CHANGE and ad > 1.0
    if side == "SELL": return change < -MIN_NIFTY_CHANGE and ad < 1.0
    return False

def candle_gate(side: str, previous_candle_open: float, previous_candle_close: float) -> bool:
    """Require the last completed candle to confirm direction."""
    try: op, cl = float(previous_candle_open), float(previous_candle_close)
    except (TypeError, ValueError): return False
    if side == "BUY": return cl > op
    if side == "SELL": return cl < op
    return False

def position_size(entry: float, stop_loss: float) -> Optional[tuple[int, float, float]]:
    try: risk_per_share = abs(float(entry) - float(stop_loss))
    except (TypeError, ValueError): return None
    if risk_per_share <= 0: return None
    quantity = max(1, int((MIN_RISK + risk_per_share - 1e-12) // risk_per_share))
    actual_risk = quantity * risk_per_share
    if actual_risk < MIN_RISK - 1e-9 or actual_risk > MAX_RISK + 1e-9: return None
    return quantity, risk_per_share, actual_risk

def make_signal(strategy: str, side: str, symbol: str, entry: float, stop_loss: float,
                nifty500_change_pct: float, ad_ratio: float, reason: str,
                previous_candle_open: float, previous_candle_close: float) -> Optional[TradeSignal]:
    if not market_gate(side, nifty500_change_pct, ad_ratio): return None
    if not candle_gate(side, previous_candle_open, previous_candle_close): return None
    try: entry, stop_loss = float(entry), float(stop_loss)
    except (TypeError, ValueError): return None
    if side == "BUY":
        if stop_loss >= entry: return None
        target = entry + (entry - stop_loss) * RR
    elif side == "SELL":
        if stop_loss <= entry: return None
        target = entry - (stop_loss - entry) * RR
    else: return None
    sizing = position_size(entry, stop_loss)
    if sizing is None: return None
    quantity, risk_per_share, actual_risk = sizing
    color = "GREEN" if float(previous_candle_close) > float(previous_candle_open) else "RED"
    return TradeSignal(strategy, side, str(symbol).upper(), round(entry, 4), round(stop_loss, 4),
        round(target, 4), round(risk_per_share, 4), quantity, round(actual_risk, 2), RR,
        round(float(nifty500_change_pct), 4), round(float(ad_ratio), 4),
        round(float(previous_candle_open), 4), round(float(previous_candle_close), 4), color,
        reason, "Exit at SL or 1.25R target; force square-off at 15:00 IST")

def evaluate_s1(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdh_swept=False, pdl_swept=False, nifty500_change_pct=0.0, ad_ratio=0.0,
                previous_candle_open=None, previous_candle_close=None):
    if previous_candle_open is None or previous_candle_close is None: return None
    if side == "BUY" and today_open > pdh and pdh_swept and ltp >= today_open:
        return make_signal("S1", side, symbol, ltp, today_low, nifty500_change_pct, ad_ratio,
            "Open > PDH → Low < PDH → LTP returned to Open", previous_candle_open, previous_candle_close)
    if side == "SELL" and today_open < pdl and pdl_swept and ltp <= today_open:
        return make_signal("S1", side, symbol, ltp, today_high, nifty500_change_pct, ad_ratio,
            "Open < PDL → High > PDL → LTP returned to Open", previous_candle_open, previous_candle_close)
    return None

def evaluate_s2(symbol, side, pdh, pdl, pullback_low, pullback_high, ltp,
                breakout_seen=False, nifty500_change_pct=0.0, ad_ratio=0.0,
                previous_candle_open=None, previous_candle_close=None):
    if previous_candle_open is None or previous_candle_close is None: return None
    if side == "BUY" and breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh:
        return make_signal("S2", side, symbol, ltp, pullback_low, nifty500_change_pct, ad_ratio,
            "Break above PDH → pullback to PDH → holds/reclaims", previous_candle_open, previous_candle_close)
    if side == "SELL" and breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl:
        return make_signal("S2", side, symbol, ltp, pullback_high, nifty500_change_pct, ad_ratio,
            "Break below PDL → pullback to PDL → fails/holds below", previous_candle_open, previous_candle_close)
    return None

def evaluate_s3(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdl_swept=False, pdh_swept=False, nifty500_change_pct=0.0, ad_ratio=0.0,
                previous_candle_open=None, previous_candle_close=None):
    if previous_candle_open is None or previous_candle_close is None: return None
    if side == "BUY" and today_open > pdl and pdl_swept and ltp >= today_open:
        return make_signal("S3", side, symbol, ltp, today_low, nifty500_change_pct, ad_ratio,
            "Open > PDL → Low < PDL → LTP reclaimed Open", previous_candle_open, previous_candle_close)
    if side == "SELL" and today_open < pdh and pdh_swept and ltp <= today_open:
        return make_signal("S3", side, symbol, ltp, today_high, nifty500_change_pct, ad_ratio,
            "Open < PDH → High > PDH → LTP reclaimed below Open", previous_candle_open, previous_candle_close)
    return None

def evaluate_s4(symbol, side, today_high, today_low, prior_intraday_high, prior_intraday_low, ltp,
                nifty500_change_pct=0.0, ad_ratio=0.0, previous_candle_open=None, previous_candle_close=None):
    if previous_candle_open is None or previous_candle_close is None: return None
    if side == "BUY" and prior_intraday_high is not None and ltp > float(prior_intraday_high):
        stop = float(prior_intraday_low) if prior_intraday_low is not None else float(today_low)
        return make_signal("S4", side, symbol, ltp, stop, nifty500_change_pct, ad_ratio,
            "LTP broke the previously formed intraday High", previous_candle_open, previous_candle_close)
    if side == "SELL" and prior_intraday_low is not None and ltp < float(prior_intraday_low):
        stop = float(prior_intraday_high) if prior_intraday_high is not None else float(today_high)
        return make_signal("S4", side, symbol, ltp, stop, nifty500_change_pct, ad_ratio,
            "LTP broke the previously formed intraday Low", previous_candle_open, previous_candle_close)
    return None

def evaluate_s5(symbol, side, pdh, pdl, ltp, nifty500_change_pct=0.0, ad_ratio=0.0,
                previous_candle_open=None, previous_candle_close=None):
    if previous_candle_open is None or previous_candle_close is None: return None
    if side == "BUY" and ltp > pdh:
        return make_signal("S5", side, symbol, ltp, pdh, nifty500_change_pct, ad_ratio,
            "LTP broke above PDH", previous_candle_open, previous_candle_close)
    if side == "SELL" and ltp < pdl:
        return make_signal("S5", side, symbol, ltp, pdl, nifty500_change_pct, ad_ratio,
            "LTP broke below PDL", previous_candle_open, previous_candle_close)
    return None

STRATEGY_DEFINITIONS = {
 "S1":{"name":"PDH/PDL Sweep + Open Reclaim","entry":"BUY: Open > PDH → Low < PDH → LTP returns to Open. SELL: Open < PDL → High > PDL → LTP returns to Open.","sl":"Today's Low / Today's High at entry","target":"1.25R"},
 "S2":{"name":"PDH/PDL Breakout + Retest","entry":"BUY: break PDH → pullback to PDH → hold. SELL: break PDL → pullback to PDL → fail below.","sl":"Retest pullback Low / High","target":"1.25R"},
 "S3":{"name":"PDL/PDH Sweep + Open Reclaim","entry":"BUY: Open > PDL → Low < PDL → return to Open. SELL: Open < PDH → High > PDH → return below Open.","sl":"Today's Low / Today's High at entry","target":"1.25R"},
 "S4":{"name":"Intraday High/Low Breakout","entry":"BUY: LTP breaks formed intraday High. SELL: LTP breaks formed intraday Low.","sl":"Previous intraday Low / High","target":"1.25R"},
 "S5":{"name":"Direct PDH/PDL Breakout","entry":"BUY: LTP > PDH. SELL: LTP < PDL.","sl":"PDH / PDL","target":"1.25R"},
}

def evaluate(strategy: str, **kwargs) -> Optional[TradeSignal]:
    fn={"S1":evaluate_s1,"S2":evaluate_s2,"S3":evaluate_s3,"S4":evaluate_s4,"S5":evaluate_s5}.get(str(strategy).upper().strip())
    if fn is None: raise ValueError(f"Unknown price-action strategy: {strategy}")
    return fn(**kwargs)
