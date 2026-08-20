"""Temporary paper-only alignment test: BUY above open / SELL below open.

This does not weaken the normal S1-S5 strategies. It adds a separate TEST
signal only when the master market alignment is already PASS. The test is
intended to verify the live price -> signal -> risk -> paper execution path.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TEST_STRATEGY = "TEST"
RR = 1.25
MIN_RISK = 1400.0
MAX_RISK = 1500.0
CAPITAL = 250000.0


def install(MasterEngine):
    if getattr(MasterEngine, "_alignment_test_trade_installed", False):
        return MasterEngine

    original_init = MasterEngine.__init__
    original_scan = MasterEngine.scan

    def init_with_test(self):
        original_init(self)
        self.daily_counts.setdefault(TEST_STRATEGY, 0)
        self.daily_pnl_by_strategy.setdefault(TEST_STRATEGY, 0.0)

    def make_test_signal(self, snap):
        if not (snap.get("buy_alignment") or snap.get("sell_alignment")):
            return None
        if not snap.get("ad_complete") or not snap.get("sector", {}).get("available"):
            return None

        for _, ref in self.references.iterrows():
            symbol = str(ref["Symbol"]).upper()
            d = snap.get("intraday", {}).get(symbol)
            if d is None or d.empty:
                continue
            prev = d.iloc[-1]
            dhan = (snap.get("dhan_quotes") or {}).get(symbol, {})
            entry = float(dhan.get("LTP") or prev["Close"])
            today_open = float(dhan.get("TodayOpen") or d.iloc[0]["Open"])
            today_low = float(dhan.get("TodayLow") or d["Low"].min())
            today_high = float(dhan.get("TodayHigh") or d["High"].max())
            if entry <= 0 or today_open <= 0:
                continue

            if snap.get("buy_alignment") and entry > today_open:
                side = "BUY"
                stop = today_low
                if stop >= entry or stop <= 0:
                    continue
                reason = "TEST: all master alignment PASS + LTP above today's open"
                target = entry + RR * (entry - stop)
            elif snap.get("sell_alignment") and entry < today_open:
                side = "SELL"
                stop = today_high
                if stop <= entry or stop <= 0:
                    continue
                reason = "TEST: all master alignment PASS + LTP below today's open"
                target = entry - RR * (stop - entry)
            else:
                continue

            risk_per_share = abs(entry - stop)
            if risk_per_share <= 0:
                continue
            max_qty_cap = int(CAPITAL // entry)
            min_qty = max(1, int((MIN_RISK + risk_per_share - 1e-12) // risk_per_share))
            max_qty = min(max_qty_cap, int(MAX_RISK // risk_per_share))
            if max_qty < min_qty:
                continue
            qty = max_qty
            risk = qty * risk_per_share
            if not (MIN_RISK <= risk <= MAX_RISK):
                continue
            now = datetime.now(IST).isoformat(timespec="seconds")
            return {
                "strategy": TEST_STRATEGY,
                "strategy_name": "ALIGNMENT TEST — ABOVE/BELOW OPEN",
                "signal": side,
                "side": side,
                "symbol": symbol,
                "entry": round(entry, 4),
                "stop_loss": round(stop, 4),
                "target": round(target, 4),
                "risk_per_share": round(risk_per_share, 4),
                "quantity": qty,
                "actual_risk": round(risk, 2),
                "capital_used": round(entry * qty, 2),
                "rr": RR,
                "nifty500_change_pct": snap.get("nifty_change"),
                "sector_alignment_pct": snap.get("sector", {}).get("alignment_pct"),
                "ad_ratio": snap.get("ad_ratio"),
                "previous_candle_open": float(prev["Open"]),
                "previous_candle_close": float(prev["Close"]),
                "previous_candle_color": "GREEN" if float(prev["Close"]) > float(prev["Open"]) else "RED",
                "entry_reason": reason,
                "reason": reason,
                "setup_type": TEST_STRATEGY,
                "entry_time": now,
                "signal_status": "TEST_ELIGIBLE",
                "price_source": "Dhan" if dhan else "1m close",
                "exit_rules": "Exit at SL or 1.25R target; force square-off at 15:00 IST",
            }
        return None

    def scan_with_test(self):
        result = original_scan(self)
        # Only test when normal S1-S5 generated no signal. This avoids changing
        # normal strategy selection when a real setup exists.
        if result or self.daily_counts.get(TEST_STRATEGY, 0) >= 1:
            return result
        test_signal = make_test_signal(self, self.last_snapshot or {})
        if test_signal:
            result = [test_signal]
            self.last_signals = result
            self.diagnostics["final_signals"] = 1
            self.diagnostics["signals_by_strategy"][TEST_STRATEGY] = 1
            self.diagnostics["test_trade"] = "ELIGIBLE"
        else:
            self.diagnostics["test_trade"] = "NOT_ELIGIBLE"
        try:
            self._write_diagnostics()
        except Exception:
            pass
        return result

    MasterEngine.__init__ = init_with_test
    MasterEngine.scan = scan_with_test
    MasterEngine._make_alignment_test_signal = make_test_signal
    MasterEngine._alignment_test_trade_installed = True
    return MasterEngine
