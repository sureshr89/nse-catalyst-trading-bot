"""Runtime for Strategy 2: gap extension reversal BUY and SELL."""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import (
    TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MAX_OPEN_POSITIONS,
    DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES,
    MIN_REQUIRED_RISK, MAX_RISK_PER_TRADE, MIN_RR_RATIO,
)
from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine
from strategy.strategy2_risk_engine import Strategy2RiskEngine
from papertrade.strategy2_paper_engine import Strategy2PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal

INDIA_TZ = ZoneInfo("Asia/Kolkata")
STRATEGY2_TRADES = Path("outputs/strategy2_trades.csv")
MAX_TRIGGER_AGE_SECONDS = 120


class Strategy2Runtime:
    def __init__(self, scanner):
        self.scanner = scanner
        self.strategy = GapExtensionReversalEngine(TRADING_START, LAST_ENTRY_TIME, 1.25)
        self.risk_engine = Strategy2RiskEngine()
        self.paper_engine = Strategy2PaperTradeEngine()
        self.journal = TradeJournal(str(STRATEGY2_TRADES), "outputs/strategy2_signals.csv")
        self.processed = set()
        self.last_signals = []
        self.cooldown_until = None
        self.daily_pnl = 0.0
        self.diagnostics = {
            "strategy": self.strategy.strategy_id,
            "strategy_name": self.strategy.strategy_name,
            "strategy_version": self.strategy.strategy_version,
            "signals": 0,
            "candidates": 0,
            "qualified": 0,
            "buy_candidates": 0,
            "sell_candidates": 0,
            "buy_qualified": 0,
            "sell_qualified": 0,
            "risk_adjusted": 0,
            "rejections": {},
        }
        self._restore_session()
        self._restore_processed()
        self._write_diagnostics()

    @staticmethod
    def _now():
        return datetime.now(INDIA_TZ)

    @staticmethod
    def _date_ist(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return (parsed.tz_localize(INDIA_TZ) if getattr(parsed, "tzinfo", None) is None else parsed.tz_convert(INDIA_TZ)).date()
        except Exception:
            return None

    @staticmethod
    def _trade_key(trade):
        if not isinstance(trade, dict):
            return None
        trade_id = str(trade.get("trade_id", "")).strip().upper()
        if trade_id:
            return ("ID", trade_id)
        symbol = str(trade.get("symbol", "")).strip().upper()
        entry = str(trade.get("entry_time", "")).strip()
        exit_time = str(trade.get("exit_time", "")).strip()
        if not symbol or not exit_time:
            return None
        return ("LEGACY", symbol, str(trade.get("signal", "")).strip().upper(), entry, exit_time, str(trade.get("exit_price", "")).strip())

    def _today_closed_trades(self):
        """Union journal + paper state so a restart cannot lose realized P&L."""
        today = self._now().date()
        merged = {}

        try:
            df = self.journal.get_trades()
            if not df.empty:
                for _, row in df.iterrows():
                    trade = dict(row)
                    if str(trade.get("status", "")).upper() != "CLOSED":
                        continue
                    if self._date_ist(trade.get("exit_time")) != today:
                        continue
                    key = self._trade_key(trade)
                    if key is not None:
                        merged[key] = trade
        except Exception as error:
            print(f"Strategy 2 journal recovery skipped: {type(error).__name__}: {error}")

        for trade in list(self.paper_engine.closed_positions):
            if not isinstance(trade, dict) or str(trade.get("status", "")).upper() != "CLOSED":
                continue
            if self._date_ist(trade.get("exit_time")) != today:
                continue
            key = self._trade_key(trade)
            if key is not None:
                merged[key] = dict(trade)
        return list(merged.values())

    def _restore_session(self):
        try:
            closed = self._today_closed_trades()
            if not closed:
                return
            self.daily_pnl = round(sum(float(pd.to_numeric(pd.Series([trade.get("pnl", 0)]), errors="coerce").fillna(0).iloc[0]) for trade in closed), 2)
            stops = [trade for trade in closed if str(trade.get("exit_reason", "")).upper() == "STOP_LOSS"]
            if not stops:
                return
            stop_times = [pd.to_datetime(trade.get("exit_time"), errors="coerce") for trade in stops]
            stop_times = [value for value in stop_times if not pd.isna(value)]
            if not stop_times:
                return
            last_stop = max(stop_times)
            last_stop = last_stop.tz_localize(INDIA_TZ) if getattr(last_stop, "tzinfo", None) is None else last_stop.tz_convert(INDIA_TZ)
            end = last_stop.to_pydatetime() + timedelta(minutes=COOLDOWN_MINUTES)
            if end > self._now():
                self.cooldown_until = end.replace(tzinfo=None)
        except Exception as error:
            print(f"Strategy 2 session restore skipped: {type(error).__name__}: {error}")

    def _restore_processed(self):
        try:
            df = self.journal.get_signals()
            if df.empty or "candidate_id" not in df.columns:
                return
            today = self._now().date()
            for _, row in df.iterrows():
                if self._date_ist(row.get("timestamp")) == today and str(row.get("candidate_id", "")).strip():
                    self.processed.add(str(row["candidate_id"]).strip())
        except Exception:
            pass

    def _write_diagnostics(self):
        payload = dict(self.diagnostics)
        payload["timestamp"] = self._now().isoformat(timespec="seconds")
        payload["open_positions"] = len(self.paper_engine.open_positions)
        payload["available_capital"] = self.paper_engine.available_capital
        payload["used_capital"] = self.paper_engine.used_capital
        payload["total_capital"] = self.paper_engine.total_capital
        payload["daily_pnl"] = self.daily_pnl
        payload["cooldown_active"] = bool(self.cooldown_until and self._now().replace(tzinfo=None) < self.cooldown_until)
        path = Path("outputs/strategy2_diagnostics.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _reject(self, reason):
        key = str(reason).strip().lower().replace(" ", "_")
        self.diagnostics["rejections"][key] = self.diagnostics["rejections"].get(key, 0) + 1

    def _normalize_risk(self, signal):
        """Widen only an impractically tight stop so the new trade risks about Rs 1,450.

        Existing/open positions are never touched. This is applied only to a new signal
        immediately before risk approval, using the capital actually available at that time.
        If the widened stop would violate the minimum 1.25R rule, the signal is rejected.
        """
        try:
            entry = float(signal.get("entry"))
            stop = float(signal.get("stop_loss"))
            target = float(signal.get("target"))
            side = str(signal.get("signal", "")).upper()
            available = float(self.paper_engine.available_capital)
        except (TypeError, ValueError):
            return False
        if entry <= 0 or stop <= 0 or target <= 0 or available <= 0:
            return False

        distance = abs(stop - entry)
        if distance <= 0:
            return False
        capital_qty = int(available // entry)
        if capital_qty <= 0:
            self._reject("risk_no_capital_for_share")
            return False
        max_risk_qty = int(float(MAX_RISK_PER_TRADE) // distance)
        quantity = min(max_risk_qty, capital_qty)
        if quantity <= 0:
            self._reject("risk_no_valid_quantity")
            return False
        raw_risk = round(distance * quantity, 2)

        # Keep the strategy's original structural stop when it already uses the
        # intended risk band. Only widen a stop that would otherwise risk < Rs 1,400.
        if raw_risk >= float(MIN_REQUIRED_RISK):
            signal.setdefault("original_stop_loss", round(stop, 4))
            signal["risk_adjusted"] = False
            signal["risk_target"] = round((float(MIN_REQUIRED_RISK) + float(MAX_RISK_PER_TRADE)) / 2.0, 2)
            return True

        risk_target = (float(MIN_REQUIRED_RISK) + float(MAX_RISK_PER_TRADE)) / 2.0
        desired_distance = risk_target / quantity
        if side == "SELL":
            adjusted_stop = max(stop, entry + desired_distance)
            reward_per_share = entry - target
        elif side == "BUY":
            adjusted_stop = min(stop, entry - desired_distance)
            reward_per_share = target - entry
        else:
            return False

        adjusted_distance = abs(adjusted_stop - entry)
        adjusted_risk = round(adjusted_distance * quantity, 2)
        rr = reward_per_share / adjusted_distance if adjusted_distance > 0 else 0.0
        if adjusted_risk > float(MAX_RISK_PER_TRADE) + 0.01:
            self._reject("risk_adjustment_over_max")
            return False
        if adjusted_risk < float(MIN_REQUIRED_RISK) - 0.01:
            self._reject("risk_adjustment_below_min")
            return False
        if rr < float(MIN_RR_RATIO):
            self._reject("risk_adjustment_rr")
            return False

        signal["original_stop_loss"] = round(stop, 4)
        signal["stop_loss"] = round(adjusted_stop, 4)
        signal["risk_adjusted"] = True
        signal["risk_target"] = round(risk_target, 2)
        signal["estimated_quantity"] = int(quantity)
        signal["estimated_risk"] = adjusted_risk
        signal["risk_reward"] = round(rr, 4)
        self.diagnostics["risk_adjusted"] += 1
        return True

    def _open_signal(self, signal, rank):
        trigger = pd.to_datetime(signal.get("trigger_time"), errors="coerce")
        if pd.isna(trigger):
            self._reject("invalid_trigger_time")
            return False
        trigger = trigger.tz_localize(INDIA_TZ) if getattr(trigger, "tzinfo", None) is None else trigger.tz_convert(INDIA_TZ)
        age = (self._now() - trigger).total_seconds()
        if age > MAX_TRIGGER_AGE_SECONDS:
            self._reject("stale_trigger")
            return False
        if age < -5:
            self._reject("future_trigger")
            return False

        candidate_id = f"S2|{self._now().date().isoformat()}|{signal['symbol']}|{signal['signal']}|{signal['trigger_time']}"
        signal.update({"candidate_id": candidate_id, "entry_time": signal["trigger_time"], "open_cross_level": signal["today_open"], "priority_rank": rank, "candidate_state": "QUALIFIED", "nifty500_universe": True, "pdh_pdl_reached": False})
        if candidate_id in self.processed or self.journal.signal_exists(signal):
            self.processed.add(candidate_id)
            return False
        if self.daily_pnl <= -float(DAILY_MAX_LOSS) or self.daily_pnl >= float(DAILY_PROFIT_TARGET):
            self._reject("daily_limit")
            self.processed.add(candidate_id)
            return False
        if self.cooldown_until and self._now().replace(tzinfo=None) < self.cooldown_until:
            self._reject("cooldown")
            return False
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
            self._reject("position_limit")
            return False

        if not self._normalize_risk(signal):
            self.processed.add(candidate_id)
            return False

        risk = self.risk_engine.approve_trade(signal, available_capital=self.paper_engine.available_capital)
        self.journal.log_signal({**signal, **risk, "approved": bool(risk.get("approved")), "reason": "; ".join(map(str, risk.get("reasons", [])))})
        if not risk.get("approved"):
            self._reject("risk")
            if "CAPITAL" not in " ".join(map(str, risk.get("reasons", []))).upper():
                self.processed.add(candidate_id)
            return False

        trade = dict(signal)
        trade.update(risk)
        trade["approved"] = True
        result = self.paper_engine.open_trade(trade)
        if not result.get("opened"):
            self._rollback_registered_trade(signal["symbol"])
            self._reject("execution")
            if "capital" not in str(result.get("reason", "")).lower():
                self.processed.add(candidate_id)
            return False

        position = result.get("position")
        if position:
            self.journal.log_trade(position)
        self.processed.add(candidate_id)
        return True

    def scan(self):
        now = self._now().strftime("%H:%M")
        if now < TRADING_START or now > LAST_ENTRY_TIME:
            return []
        candidates = self.scanner.opening_candidates
        data = self.scanner.universe_market_data
        nifty_change = self.scanner._nifty_change
        if candidates is None or candidates.empty:
            self.diagnostics["candidates"] = 0
            self.last_signals = []
            self._write_diagnostics()
            return []

        rows = []
        for _, row in candidates.iterrows():
            symbol = str(row.get("Symbol", "")).upper().strip()
            setup = str(row.get("OpeningSetup", ""))
            if not symbol or setup not in {"OPEN_ABOVE_PDH", "OPEN_BELOW_PDL"}:
                continue
            stock_data = data.get(symbol)
            if stock_data is None or stock_data.empty:
                continue
            signal = self.strategy.evaluate(symbol, stock_data, row["TodayOpen"], row["PDH"], row["PreviousDayClose"], nifty_change, row["PDL"])
            if signal:
                signal["gap_percent"] = float(row.get("GapPercentFromPreviousClose", signal.get("gap_percent", 0.0)))
                signal["industry"] = row.get("Industry", "UNKNOWN")
                rows.append(signal)

        rows.sort(key=lambda x: abs(float(x.get("gap_percent", 0.0))), reverse=True)
        self.diagnostics["candidates"] = int(len(candidates))
        self.diagnostics["buy_candidates"] = int(sum(str(r.get("OpeningSetup", "")) == "OPEN_BELOW_PDL" for _, r in candidates.iterrows()))
        self.diagnostics["sell_candidates"] = int(sum(str(r.get("OpeningSetup", "")) == "OPEN_ABOVE_PDH" for _, r in candidates.iterrows()))
        self.diagnostics["qualified"] = len(rows)
        self.diagnostics["buy_qualified"] = int(sum(s.get("signal") == "BUY" for s in rows))
        self.diagnostics["sell_qualified"] = int(sum(s.get("signal") == "SELL" for s in rows))
        self.diagnostics["signals"] = 0
        self.last_signals = rows
        for rank, signal in enumerate(rows, 1):
            if self._open_signal(signal, rank):
                self.diagnostics["signals"] += 1
        self._write_diagnostics()
        return rows

    def process_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            candle = self.scanner.price_data.get_latest_available_1m(symbol)
            if candle is None:
                continue
            closed = self.paper_engine.process_candle(symbol, candle)
            if closed:
                self.daily_pnl = round(self.daily_pnl + float(closed.get("pnl", 0) or 0), 2)
                self.journal.log_trade(closed)
                if str(closed.get("exit_reason", "")).upper() == "STOP_LOSS":
                    self.cooldown_until = self._now().replace(tzinfo=None) + timedelta(minutes=COOLDOWN_MINUTES)
        self._write_diagnostics()

    def run_cycle(self):
        self.process_positions()
        return self.scan()

    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            candle = self.scanner.price_data.get_latest_available_1m(symbol)
            if candle is None:
                continue
            closed = self.paper_engine.close_position(symbol, float(candle["Close"]), candle["Datetime"], "SQUARE_OFF")
            if closed:
                self.daily_pnl = round(self.daily_pnl + float(closed.get("pnl", 0) or 0), 2)
                self.journal.log_trade(closed)
        self._write_diagnostics()
