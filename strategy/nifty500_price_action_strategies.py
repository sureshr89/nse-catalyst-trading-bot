"""Five NIFTY 500 intraday OHLC/PDH/PDL price-action strategies.

Design rules shared by S1-S5:
- Universe: NIFTY 500.
- BUY market gate: NIFTY 500 change > 0% AND A/D ratio > 1.
- SELL market gate: NIFTY 500 change < 0% AND A/D ratio < 1.
- Inputs are today's Open/High/Low/LTP plus PDH/PDL and intraday running levels.
- No sector filter and no technical indicators.
- Entries are live-LTP triggers; no candle-close confirmation.
- SL/target are calculated from information available at entry only.
- Target is 1.25R.
- Position risk must be between ₹1,400 and ₹1,500; otherwise no trade.
- Mandatory end-of-day square-off is 15:00 IST.

The functions are deliberately pure: the scanner supplies the latest live values and
its persisted setup state. No future day's data can be used by this module.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

RR = 1.25
MIN_RISK = 1400.0
MAX_RISK = 1500.0
SQUARE_OFF_TIME = "15:00"


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
    entry_reason: str
    exit_rules: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def market_gate(side: str, nifty500_change_pct: float, ad_ratio: float) -> bool:
    """Hard common market filter. Missing/invalid values never pass."""
    try:
        change = float(nifty500_change_pct)
        ad = float(ad_ratio)
    except (TypeError, ValueError):
        return False
    if side == "BUY":
        return change > 0.0 and ad > 1.0
    if side == "SELL":
        return change < 0.0 and ad < 1.0
    return False


def position_size(entry: float, stop_loss: float) -> Optional[tuple[int, float, float]]:
    """Return quantity/risk only when total risk is ₹1,400-₹1,500 inclusive."""
    try:
        risk_per_share = abs(float(entry) - float(stop_loss))
    except (TypeError, ValueError):
        return None
    if risk_per_share <= 0:
        return None
    # Smallest quantity that reaches the minimum risk band.
    quantity = int((MIN_RISK + risk_per_share - 1e-12) // risk_per_share)
    if quantity < 1:
        quantity = 1
    actual_risk = quantity * risk_per_share
    if actual_risk < MIN_RISK - 1e-9 or actual_risk > MAX_RISK + 1e-9:
        return None
    return quantity, risk_per_share, actual_risk


def make_signal(strategy: str, side: str, symbol: str, entry: float, stop_loss: float,
                nifty500_change_pct: float, ad_ratio: float, reason: str) -> Optional[TradeSignal]:
    if not market_gate(side, nifty500_change_pct, ad_ratio):
        return None
    try:
        entry = float(entry); stop_loss = float(stop_loss)
    except (TypeError, ValueError):
        return None
    if side == "BUY":
        if stop_loss >= entry:
            return None
        target = entry + (entry - stop_loss) * RR
    elif side == "SELL":
        if stop_loss <= entry:
            return None
        target = entry - (stop_loss - entry) * RR
    else:
        return None
    sizing = position_size(entry, stop_loss)
    if sizing is None:
        return None
    quantity, risk_per_share, actual_risk = sizing
    return TradeSignal(strategy, side, str(symbol).upper(), round(entry, 4), round(stop_loss, 4),
                        round(target, 4), round(risk_per_share, 4), quantity, round(actual_risk, 2),
                        RR, round(float(nifty500_change_pct), 4), round(float(ad_ratio), 4),
                        reason, "Exit at SL or 1.25R target; force square-off at 15:00 IST")


def evaluate_s1(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdh_swept=False, pdl_swept=False, nifty500_change_pct=0.0, ad_ratio=0.0):
    """S1: PDH/PDL sweep then return to today's Open."""
    if side == "BUY" and today_open > pdh and pdh_swept and ltp >= today_open:
        return make_signal("S1", side, symbol, ltp, today_low, nifty500_change_pct, ad_ratio,
                           "Open > PDH → intraday Low < PDH → live LTP returned to Today's Open")
    if side == "SELL" and today_open < pdl and pdl_swept and ltp <= today_open:
        return make_signal("S1", side, symbol, ltp, today_high, nifty500_change_pct, ad_ratio,
                           "Open < PDL → intraday High > PDL → live LTP returned to Today's Open")
    return None


def evaluate_s2(symbol, side, pdh, pdl, pullback_low, pullback_high, ltp,
                breakout_seen=False, nifty500_change_pct=0.0, ad_ratio=0.0):
    """S2: PDH/PDL breakout and live retest/reclaim."""
    if side == "BUY" and breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh:
        return make_signal("S2", side, symbol, ltp, pullback_low, nifty500_change_pct, ad_ratio,
                           "Live break above PDH → pullback to PDH → live price holds/reclaims PDH")
    if side == "SELL" and breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl:
        return make_signal("S2", side, symbol, ltp, pullback_high, nifty500_change_pct, ad_ratio,
                           "Live break below PDL → pullback to PDL → live price holds/reclaims below PDL")
    return None


def evaluate_s3(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdl_swept=False, pdh_swept=False, nifty500_change_pct=0.0, ad_ratio=0.0):
    """S3: PDL/PDH sweep followed by return through today's Open."""
    if side == "BUY" and today_open > pdl and pdl_swept and ltp >= today_open:
        return make_signal("S3", side, symbol, ltp, today_low, nifty500_change_pct, ad_ratio,
                           "Open > PDL → intraday Low < PDL → live LTP reclaimed Today's Open")
    if side == "SELL" and today_open < pdh and pdh_swept and ltp <= today_open:
        return make_signal("S3", side, symbol, ltp, today_high, nifty500_change_pct, ad_ratio,
                           "Open < PDH → intraday High > PDH → live LTP reclaimed below Today's Open")
    return None


def evaluate_s4(symbol, side, today_high, today_low, prior_intraday_high, prior_intraday_low, ltp,
                nifty500_change_pct=0.0, ad_ratio=0.0):
    """S4: break of the already-formed intraday high/low (no future level)."""
    if side == "BUY" and prior_intraday_high is not None and ltp > float(prior_intraday_high):
        stop = float(prior_intraday_low) if prior_intraday_low is not None else float(today_low)
        return make_signal("S4", side, symbol, ltp, stop, nifty500_change_pct, ad_ratio,
                           "Live LTP broke the previously formed intraday High")
    if side == "SELL" and prior_intraday_low is not None and ltp < float(prior_intraday_low):
        stop = float(prior_intraday_high) if prior_intraday_high is not None else float(today_high)
        return make_signal("S4", side, symbol, ltp, stop, nifty500_change_pct, ad_ratio,
                           "Live LTP broke the previously formed intraday Low")
    return None


def evaluate_s5(symbol, side, pdh, pdl, ltp, nifty500_change_pct=0.0, ad_ratio=0.0):
    """S5: direct live breakout of PDH/PDL."""
    if side == "BUY" and ltp > pdh:
        return make_signal("S5", side, symbol, ltp, pdh, nifty500_change_pct, ad_ratio,
                           "Live LTP broke above PDH")
    if side == "SELL" and ltp < pdl:
        return make_signal("S5", side, symbol, ltp, pdl, nifty500_change_pct, ad_ratio,
                           "Live LTP broke below PDL")
    return None


STRATEGY_DEFINITIONS = {
    "S1": {"name": "PDH/PDL Sweep + Open Reclaim", "entry": "BUY: Open > PDH, Low < PDH, LTP returns to Open. SELL: Open < PDL, High > PDL, LTP returns to Open.", "sl": "Today's Low / Today's High at entry", "target": "1.25R"},
    "S2": {"name": "PDH/PDL Breakout + Retest", "entry": "BUY: break PDH, pull back to PDH, hold/reclaim. SELL: break PDL, pull back to PDL, hold/fail.", "sl": "Retest pullback Low / High", "target": "1.25R"},
    "S3": {"name": "PDL/PDH Sweep + Open Reclaim", "entry": "BUY: Open > PDL, Low < PDL, return to Open. SELL: Open < PDH, High > PDH, return below Open.", "sl": "Today's Low / Today's High at entry", "target": "1.25R"},
    "S4": {"name": "Intraday High/Low Breakout", "entry": "BUY: live LTP breaks previously formed intraday High. SELL: live LTP breaks previously formed intraday Low.", "sl": "Previous intraday Low / High", "target": "1.25R"},
    "S5": {"name": "Direct PDH/PDL Breakout", "entry": "BUY: live LTP > PDH. SELL: live LTP < PDL.", "sl": "PDH / PDL", "target": "1.25R"},
}


def evaluate(strategy: str, **kwargs) -> Optional[TradeSignal]:
    """Dispatch one strategy without mixing strategy rules."""
    key = str(strategy).upper().strip()
    fn = {"S1": evaluate_s1, "S2": evaluate_s2, "S3": evaluate_s3, "S4": evaluate_s4, "S5": evaluate_s5}.get(key)
    if fn is None:
        raise ValueError(f"Unknown price-action strategy: {strategy}")
    return fn(**kwargs)
