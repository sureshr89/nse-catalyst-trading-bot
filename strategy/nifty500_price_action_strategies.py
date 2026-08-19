"""Five NIFTY 500 intraday OHLC/PDH/PDL paper-trading strategies."""
from dataclasses import dataclass, asdict
from typing import Any, Dict

RR = 1.25
MIN_RISK = 1400.0
MAX_RISK = 1500.0
CAPITAL_PER_TRADE = 250000.0

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
    capital_used: float
    rr: float
    nifty500_change_pct: float
    sector_alignment_pct: float
    ad_ratio: float
    previous_candle_open: float
    previous_candle_close: float
    previous_candle_color: str
    entry_reason: str
    exit_rules: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _finite_positive(value):
    try:
        value = float(value)
        return value > 0 and value == value and value != float("inf")
    except (TypeError, ValueError):
        return False


def market_gate(side, nifty500_change_pct, sector_alignment_pct, ad_ratio, ad_coverage=500):
    try:
        change = float(nifty500_change_pct)
        sector = float(sector_alignment_pct)
        ad = float(ad_ratio)
    except (TypeError, ValueError):
        return False
    if int(ad_coverage) != 500:
        return False
    if side == "BUY":
        return change > 0 and sector > 0 and ad > 1
    if side == "SELL":
        return change < 0 and sector < 0 and ad < 1
    return False


def candle_gate(side, previous_candle_open, previous_candle_close):
    try:
        op, cl = float(previous_candle_open), float(previous_candle_close)
    except (TypeError, ValueError):
        return False
    if op <= 0 or cl <= 0:
        return False
    return cl > op if side == "BUY" else cl < op if side == "SELL" else False


def position_size(entry, stop_loss):
    try:
        entry, stop_loss = float(entry), float(stop_loss)
        risk_per_share = abs(entry - stop_loss)
    except (TypeError, ValueError):
        return None
    if not _finite_positive(entry) or not _finite_positive(risk_per_share):
        return None
    max_capital_qty = int(CAPITAL_PER_TRADE // entry)
    if max_capital_qty < 1:
        return None
    min_qty = max(1, int((MIN_RISK + risk_per_share - 1e-12) // risk_per_share))
    max_qty = min(max_capital_qty, int(MAX_RISK // risk_per_share))
    if min_qty > max_qty:
        return None
    qty = max_qty
    actual_risk = qty * risk_per_share
    if not MIN_RISK <= actual_risk <= MAX_RISK:
        return None
    return qty, risk_per_share, actual_risk, qty * entry


def make_signal(strategy, side, symbol, entry, stop_loss, nifty500_change_pct,
                sector_alignment_pct, ad_ratio, ad_coverage, reason,
                previous_candle_open, previous_candle_close):
    if not market_gate(side, nifty500_change_pct, sector_alignment_pct, ad_ratio, ad_coverage):
        return None
    if not candle_gate(side, previous_candle_open, previous_candle_close):
        return None
    try:
        entry, stop_loss = float(entry), float(stop_loss)
    except (TypeError, ValueError):
        return None
    if not _finite_positive(entry) or not _finite_positive(stop_loss):
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
    qty, risk_per_share, actual_risk, capital = sizing
    color = "GREEN" if float(previous_candle_close) > float(previous_candle_open) else "RED"
    return TradeSignal(
        strategy=str(strategy).upper(), side=side, symbol=str(symbol).upper(),
        entry=round(entry, 4), stop_loss=round(stop_loss, 4), target=round(target, 4),
        risk_per_share=round(risk_per_share, 4), quantity=qty,
        actual_risk=round(actual_risk, 2), capital_used=round(capital, 2), rr=RR,
        nifty500_change_pct=round(float(nifty500_change_pct), 4),
        sector_alignment_pct=round(float(sector_alignment_pct), 4),
        ad_ratio=round(float(ad_ratio), 4),
        previous_candle_open=round(float(previous_candle_open), 4),
        previous_candle_close=round(float(previous_candle_close), 4),
        previous_candle_color=color, entry_reason=reason,
        exit_rules="Exit at SL or 1.25R target; force square-off at 15:00 IST",
    )


def evaluate_s1(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdh_swept=False, pdl_swept=False, **g):
    po, pc = g.get("previous_candle_open"), g.get("previous_candle_close")
    if po is None or pc is None:
        return None
    if side == "BUY" and today_open > pdh and pdh_swept and ltp >= today_open:
        return make_signal("S1", side, symbol, ltp, today_low, reason="Open > PDH -> price swept below PDH -> reclaim of Open", previous_candle_open=po, previous_candle_close=pc, **g)
    if side == "SELL" and today_open < pdl and pdl_swept and ltp <= today_open:
        return make_signal("S1", side, symbol, ltp, today_high, reason="Open < PDL -> price swept above PDL -> rejection of Open", previous_candle_open=po, previous_candle_close=pc, **g)
    return None


def evaluate_s2(symbol, side, pdh, pdl, pullback_low, pullback_high, ltp, breakout_seen=False, **g):
    po, pc = g.get("previous_candle_open"), g.get("previous_candle_close")
    if po is None or pc is None:
        return None
    if side == "BUY" and breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh:
        return make_signal("S2", side, symbol, ltp, pullback_low, reason="Break PDH -> pullback to PDH -> reclaim", previous_candle_open=po, previous_candle_close=pc, **g)
    if side == "SELL" and breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl:
        return make_signal("S2", side, symbol, ltp, pullback_high, reason="Break PDL -> pullback to PDL -> fail below", previous_candle_open=po, previous_candle_close=pc, **g)
    return None


def evaluate_s3(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdl_swept=False, pdh_swept=False, **g):
    po, pc = g.get("previous_candle_open"), g.get("previous_candle_close")
    if po is None or pc is None:
        return None
    if side == "BUY" and today_open > pdl and pdl_swept and ltp >= today_open:
        return make_signal("S3", side, symbol, ltp, today_low, reason="Open > PDL -> price swept below PDL -> reclaim of Open", previous_candle_open=po, previous_candle_close=pc, **g)
    if side == "SELL" and today_open < pdh and pdh_swept and ltp <= today_open:
        return make_signal("S3", side, symbol, ltp, today_high, reason="Open < PDH -> price swept above PDH -> rejection of Open", previous_candle_open=po, previous_candle_close=pc, **g)
    return None


def evaluate_s4(symbol, side, today_high, today_low, prior_intraday_high, prior_intraday_low, ltp, **g):
    po, pc = g.get("previous_candle_open"), g.get("previous_candle_close")
    if po is None or pc is None:
        return None
    if side == "BUY" and prior_intraday_high is not None and ltp > float(prior_intraday_high):
        stop = float(prior_intraday_low) if prior_intraday_low is not None else float(today_low)
        return make_signal("S4", side, symbol, ltp, stop, reason="LTP broke previously formed intraday High", previous_candle_open=po, previous_candle_close=pc, **g)
    if side == "SELL" and prior_intraday_low is not None and ltp < float(prior_intraday_low):
        stop = float(prior_intraday_high) if prior_intraday_high is not None else float(today_high)
        return make_signal("S4", side, symbol, ltp, stop, reason="LTP broke previously formed intraday Low", previous_candle_open=po, previous_candle_close=pc, **g)
    return None


def evaluate_s5(symbol, side, pdh, pdl, ltp, **g):
    po, pc = g.get("previous_candle_open"), g.get("previous_candle_close")
    if po is None or pc is None:
        return None
    if side == "BUY" and ltp > pdh:
        return make_signal("S5", side, symbol, ltp, pdh, reason="LTP broke above PDH", previous_candle_open=po, previous_candle_close=pc, **g)
    if side == "SELL" and ltp < pdl:
        return make_signal("S5", side, symbol, ltp, pdl, reason="LTP broke below PDL", previous_candle_open=po, previous_candle_close=pc, **g)
    return None


STRATEGY_DEFINITIONS = {
    "S1": {"name": "PDH/PDL Sweep + Open Reclaim", "entry": "Open beyond PDH/PDL -> sweep back through level -> reclaim/reject Open", "sl": "Today's Low / High at entry", "target": "1.25R"},
    "S2": {"name": "PDH/PDL Breakout + Retest", "entry": "Break PDH/PDL -> retest -> reclaim/fail", "sl": "Retest Low / High", "target": "1.25R"},
    "S3": {"name": "Opposite PDH/PDL Sweep + Open Reclaim", "entry": "Sweep opposite prior-day level -> reclaim/reject Open", "sl": "Today's Low / High at entry", "target": "1.25R"},
    "S4": {"name": "Intraday High/Low Breakout", "entry": "Break previously formed intraday High/Low", "sl": "Previous intraday Low / High", "target": "1.25R"},
    "S5": {"name": "Direct PDH/PDL Breakout", "entry": "Break PDH / PDL", "sl": "PDH / PDL", "target": "1.25R"},
}


def evaluate(strategy, **kwargs):
    fn = {"S1": evaluate_s1, "S2": evaluate_s2, "S3": evaluate_s3, "S4": evaluate_s4, "S5": evaluate_s5}.get(str(strategy).upper().strip())
    if fn is None:
        raise ValueError(f"Unknown price-action strategy: {strategy}")
    return fn(**kwargs)
