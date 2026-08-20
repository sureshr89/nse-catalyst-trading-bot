"""Five NIFTY 500 intraday OHLC/PDH/PDL paper-trading strategies.

This module is the pure S1-S5 signal contract.  Live sequencing/data preparation
belongs to the engine; these functions only validate the already-observed setup
and calculate a deterministic paper-trade signal.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict
import math

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
        data = asdict(self)
        data.update({"signal": data["side"], "setup_type": data["strategy"], "reason": data["entry_reason"]})
        return data


def _finite_positive(v: Any) -> bool:
    try:
        x = float(v)
        return math.isfinite(x) and x > 0
    except (TypeError, ValueError):
        return False


def market_gate(side, nifty500_change_pct, sector_alignment_pct, ad_ratio, ad_coverage=500):
    """Validate the common NIFTY-500/sector/breadth direction gate."""
    try:
        change = float(nifty500_change_pct)
        sector = float(sector_alignment_pct)
        ad = float(ad_ratio)
        coverage = int(ad_coverage)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(x) for x in (change, sector, ad)) or coverage != 500:
        return False
    if side == "BUY":
        return change > 0 and sector > 0 and ad > 1
    if side == "SELL":
        return change < 0 and sector < 0 and ad < 1
    return False


def candle_gate(side, previous_candle_open, previous_candle_close):
    """Report candle direction for diagnostics; it is NOT an entry blocker.

    The live S1/S2 implementation uses live price sequencing rather than a
    candle-close confirmation.  Keeping this helper lets existing callers/tests
    inspect candle direction without silently suppressing otherwise valid live
    setups.
    """
    try:
        op, cl = float(previous_candle_open), float(previous_candle_close)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(op) or not math.isfinite(cl) or op <= 0 or cl <= 0:
        return False
    if side == "BUY":
        return cl > op
    if side == "SELL":
        return cl < op
    return False


def position_size(entry, stop_loss):
    try:
        entry, stop_loss = float(entry), float(stop_loss)
    except (TypeError, ValueError):
        return None
    if not _finite_positive(entry) or not _finite_positive(stop_loss):
        return None
    risk_per_share = abs(entry - stop_loss)
    if not _finite_positive(risk_per_share):
        return None

    max_cap = int(CAPITAL_PER_TRADE // entry)
    if max_cap < 1:
        return None

    # Smallest whole quantity that reaches the intended risk band, subject to
    # both the per-trade capital cap and the maximum-risk ceiling.
    min_qty = max(1, math.ceil((MIN_RISK - 1e-12) / risk_per_share))
    max_qty = min(max_cap, math.floor(MAX_RISK / risk_per_share))
    if min_qty > max_qty:
        return None

    qty = min_qty
    actual_risk = qty * risk_per_share
    capital_used = qty * entry
    if not (MIN_RISK <= actual_risk <= MAX_RISK and capital_used <= CAPITAL_PER_TRADE):
        return None
    return qty, risk_per_share, actual_risk, capital_used


def make_signal(strategy, side, symbol, entry, stop_loss, nifty500_change_pct,
                sector_alignment_pct, ad_ratio, ad_coverage, reason,
                previous_candle_open, previous_candle_close):
    if not market_gate(side, nifty500_change_pct, sector_alignment_pct, ad_ratio, ad_coverage):
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
    qty, rps, risk, capital = sizing

    try:
        po, pc = float(previous_candle_open), float(previous_candle_close)
    except (TypeError, ValueError):
        return None
    if not _finite_positive(po) or not _finite_positive(pc):
        return None
    color = "GREEN" if pc > po else "RED" if pc < po else "FLAT"

    return TradeSignal(
        str(strategy).upper(), str(side).upper(), str(symbol).upper(),
        round(entry, 4), round(stop_loss, 4), round(target, 4),
        round(rps, 4), qty, round(risk, 2), round(capital, 2), RR,
        round(float(nifty500_change_pct), 4), round(float(sector_alignment_pct), 4),
        round(float(ad_ratio), 4), round(po, 4), round(pc, 4), color,
        reason,
        "Exit at SL or 1.25R target; force square-off at 15:00 IST",
    )


def _candle_kwargs(g):
    g = dict(g)
    return g, g.pop("previous_candle_open", None), g.pop("previous_candle_close", None)


def evaluate_s1(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdh_swept_down=False, pdl_swept_up=False, pdh_swept=False,
                pdl_swept=False, **g):
    g, po, pc = _candle_kwargs(g)
    if po is None or pc is None:
        return None
    try:
        today_open, pdh, pdl, today_low, today_high = map(float, (today_open, pdh, pdl, today_low, today_high))
    except (TypeError, ValueError):
        return None
    down_pdh = bool(pdh_swept_down or (pdh_swept and today_low < pdh))
    up_pdl = bool(pdl_swept_up or (pdl_swept and today_high > pdl))
    if side == "BUY" and today_open > pdh and down_pdh:
        return make_signal("S1", side, symbol, ltp, pdh, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Open > PDH -> PDH touched/swept -> live reversal", **g)
    if side == "SELL" and today_open < pdl and up_pdl:
        return make_signal("S1", side, symbol, ltp, pdl, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Open < PDL -> PDL touched/swept -> live reversal", **g)
    return None


def evaluate_s2(symbol, side, pdh, pdl, pullback_low, pullback_high, ltp,
                breakout_seen=False, **g):
    g, po, pc = _candle_kwargs(g)
    if po is None or pc is None:
        return None
    try:
        pdh, pdl, ltp = float(pdh), float(pdl), float(ltp)
        pullback_low = None if pullback_low is None else float(pullback_low)
        pullback_high = None if pullback_high is None else float(pullback_high)
    except (TypeError, ValueError):
        return None
    if side == "BUY" and breakout_seen and ltp >= pdh and pullback_low is not None and pullback_low <= pdh:
        return make_signal("S2", side, symbol, ltp, pullback_low, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Break PDH -> pullback to PDH -> reclaim", **g)
    if side == "SELL" and breakout_seen and ltp <= pdl and pullback_high is not None and pullback_high >= pdl:
        return make_signal("S2", side, symbol, ltp, pullback_high, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Break PDL -> pullback to PDL -> fail below", **g)
    return None


def evaluate_s3(symbol, side, today_open, pdh, pdl, today_low, today_high, ltp,
                pdl_swept_down=False, pdh_swept_up=False, pdh_swept=False,
                pdl_swept=False, **g):
    g, po, pc = _candle_kwargs(g)
    if po is None or pc is None:
        return None
    try:
        today_open, pdh, pdl, today_low, today_high = map(float, (today_open, pdh, pdl, today_low, today_high))
    except (TypeError, ValueError):
        return None
    down_pdl = bool(pdl_swept_down or (pdl_swept and today_low < pdl))
    up_pdh = bool(pdh_swept_up or (pdh_swept and today_high > pdh))
    inside_range = pdl < today_open < pdh
    if side == "BUY" and inside_range and down_pdl:
        return make_signal("S3", side, symbol, ltp, today_low, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Open inside PDH/PDL -> sweep below PDL -> live reclaim", **g)
    if side == "SELL" and inside_range and up_pdh:
        return make_signal("S3", side, symbol, ltp, today_high, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="Open inside PDH/PDL -> sweep above PDH -> live rejection", **g)
    return None


def evaluate_s4(symbol, side, today_high, today_low, prior_intraday_high,
                prior_intraday_low, ltp, **g):
    g, po, pc = _candle_kwargs(g)
    if po is None or pc is None:
        return None
    try:
        today_high, today_low, ltp = float(today_high), float(today_low), float(ltp)
        prior_intraday_high = None if prior_intraday_high is None else float(prior_intraday_high)
        prior_intraday_low = None if prior_intraday_low is None else float(prior_intraday_low)
    except (TypeError, ValueError):
        return None
    if side == "BUY" and prior_intraday_high is not None and ltp > prior_intraday_high:
        sl = prior_intraday_low if prior_intraday_low is not None else today_low
        return make_signal("S4", side, symbol, ltp, sl, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="LTP broke previously formed intraday High", **g)
    if side == "SELL" and prior_intraday_low is not None and ltp < prior_intraday_low:
        sl = prior_intraday_high if prior_intraday_high is not None else today_high
        return make_signal("S4", side, symbol, ltp, sl, previous_candle_open=po,
                           previous_candle_close=pc,
                           reason="LTP broke previously formed intraday Low", **g)
    return None


def evaluate_s5(symbol, side, pdh, pdl, ltp, **g):
    g, po, pc = _candle_kwargs(g)
    if po is None or pc is None:
        return None
    try:
        pdh, pdl, ltp = float(pdh), float(pdl), float(ltp)
    except (TypeError, ValueError):
        return None
    if side == "BUY" and ltp > pdh:
        return make_signal("S5", side, symbol, ltp, pdh, previous_candle_open=po,
                           previous_candle_close=pc, reason="LTP broke above PDH", **g)
    if side == "SELL" and ltp < pdl:
        return make_signal("S5", side, symbol, ltp, pdl, previous_candle_open=po,
                           previous_candle_close=pc, reason="LTP broke below PDL", **g)
    return None


STRATEGY_DEFINITIONS = {
    "S1": {"name": "PDH/PDL Sweep + Open Reclaim", "entry": "Open beyond PDH/PDL -> directional sweep -> live reversal", "sl": "PDH / PDL", "target": "1.25R"},
    "S2": {"name": "PDH/PDL Breakout + Retest", "entry": "Break PDH/PDL -> retest -> reclaim/fail", "sl": "Retest Low / High", "target": "1.25R"},
    "S3": {"name": "Opposite PDH/PDL Sweep + Open Reversal", "entry": "Open inside PDH/PDL -> sweep opposite prior-day level -> live reversal", "sl": "Today's Low / High at entry", "target": "1.25R"},
    "S4": {"name": "Intraday High/Low Breakout", "entry": "Break previously formed intraday High/Low", "sl": "Previous intraday Low / High", "target": "1.25R"},
    "S5": {"name": "Direct PDH/PDL Breakout", "entry": "Break PDH / PDL", "sl": "PDH / PDL", "target": "1.25R"},
}


def evaluate(strategy, **kwargs):
    fn = {"S1": evaluate_s1, "S2": evaluate_s2, "S3": evaluate_s3, "S4": evaluate_s4, "S5": evaluate_s5}.get(str(strategy).upper().strip())
    if fn is None:
        raise ValueError(f"Unknown price-action strategy: {strategy}")
    return fn(**kwargs)
