"""Core paper-trading orchestration for the NIFTY 500 strategies."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import threading
import pandas as pd
from config.settings import PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MAX_OPEN_POSITIONS, DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES
from scanner.scanner_engine import ScannerEngine
from strategy.risk_engine import RiskEngine
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from papertrade.missed_capital_tracker import MissedCapitalTracker
from strategy2_runtime import Strategy2Runtime

INDIA_TZ = ZoneInfo("Asia/Kolkata")
POSITION_MONITOR_SECONDS = 2.0


class TradingBot:
    """Run one NIFTY 500 paper-trading session with both strategy runtimes."""
    def __init__(self):
        if LIVE_TRADING:
            raise RuntimeError("LIVE_TRADING must be False. This application is paper trading only.")
        if not PAPER_TRADING:
            raise RuntimeError("PAPER_TRADING must be True.")
        self.scanner = ScannerEngine()
        self.risk_engine = RiskEngine()
        self.price_data = PriceData()
        self.paper_engine = PaperTradeEngine()
        self.journal = TradeJournal()
        self._restore_risk_counts_from_paper_state()
        self.missed_capital = MissedCapitalTracker(self.journal, self.price_data)
        self.running = True
        self.processed_signals = set()
        self.daily_pnl = self._restore_daily_pnl()
        self.cooldown_until = self._restore_cooldown()
        self.square_off_done = False
        self.strategy2 = Strategy2Runtime(self.scanner)
        self._monitor_thread = threading.Thread(target=self._position_monitor_loop, name="paper-position-monitor", daemon=True)
        self._monitor_thread.start()

    @staticmethod
    def _now():
        return datetime.now(INDIA_TZ)

    @staticmethod
    def _journal_ist(value):
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return pd.NaT
            if getattr(parsed, "tzinfo", None) is None:
                return parsed.tz_localize(INDIA_TZ)
            return parsed.tz_convert(INDIA_TZ)
        except Exception:
            return pd.NaT

    def current_time(self):
        return self._now().strftime("%H:%M")

    def _restore_risk_counts_from_paper_state(self):
        try:
            today = self._now().date()
            paper_counts = {}
            for trade in list(self.paper_engine.open_positions.values()) + list(self.paper_engine.closed_positions):
                if not isinstance(trade, dict):
                    continue
                entry_dt = self._journal_ist(trade.get("entry_time"))
                if pd.isna(entry_dt) or entry_dt.date() != today:
                    continue
                symbol = str(trade.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                trade_id = str(trade.get("trade_id", "")).strip()
                key = (symbol, trade_id) if trade_id else (symbol, str(trade.get("signal", "")).strip().upper(), str(trade.get("entry_time", "")).strip(), str(trade.get("entry", "")))
                paper_counts.setdefault(symbol, set()).add(key)
            for symbol, keys in paper_counts.items():
                target = len(keys)
                current = self.risk_engine.get_trade_count(symbol)
                if current < target:
                    self.risk_engine.trade_counts[symbol] = target
        except Exception as error:
            print("Paper-state risk-count recovery skipped:", error)

    @staticmethod
    def _closed_trade_key(trade, source, index=None):
        if not isinstance(trade, dict):
            return None
        trade_id = str(trade.get("trade_id", "")).strip().upper()
        if trade_id:
            return ("id", trade_id)
        symbol = str(trade.get("symbol", "")).strip().upper()
        signal = str(trade.get("signal", "")).strip().upper()
        entry = str(trade.get("entry_time", "")).strip()
        exit_time = str(trade.get("exit_time", "")).strip()
        entry_price = str(trade.get("entry", "")).strip()
        exit_price = str(trade.get("exit_price", "")).strip()
        if not symbol or not exit_time:
            return None
        return ("legacy", symbol, signal, entry, exit_time, entry_price, exit_price)

    def _today_closed_trades(self):
        today = self._now().date()
        merged = {}

        def add_trade(trade, source, index=None):
            if not isinstance(trade, dict) or str(trade.get("status", "")).upper() != "CLOSED":
                return
            exit_dt = self._journal_ist(trade.get("exit_time"))
            if pd.isna(exit_dt) or exit_dt.date() != today:
                return
            key = self._closed_trade_key(trade, source, index)
            if key is not None and (key not in merged or source == "paper"):
                merged[key] = dict(trade)

        try:
            df = self.journal.get_trades()
            if not df.empty:
                for idx, row in df.iterrows():
                    add_trade(dict(row), "journal", idx)
        except Exception as error:
            print("Journal closed-trade recovery skipped:", error)
        try:
            for trade in self.paper_engine.closed_positions:
                add_trade(trade, "paper")
        except Exception as error:
            print("Paper-state closed-trade recovery skipped:", error)
        return list(merged.values())

    def _restore_daily_pnl(self):
        try:
            return round(sum(float(pd.to_numeric(pd.Series([t.get("pnl", 0)]), errors="coerce").fillna(0).iloc[0]) for t in self._today_closed_trades()), 2)
        except Exception:
            return 0.0

    def _restore_cooldown(self):
        try:
            stops = []
            for trade in self._today_closed_trades():
                if str(trade.get("exit_reason", "")).upper() == "STOP_LOSS":
                    dt = self._journal_ist(trade.get("exit_time"))
                    if pd.notna(dt):
                        stops.append(dt)
            if not stops:
                return None
            end = max(stops).to_pydatetime() + timedelta(minutes=COOLDOWN_MINUTES)
            now = self._now()
            return end.replace(tzinfo=None) if end > now.replace(tzinfo=None) else None
        except Exception:
            return None

    def signal_key(self, signal):
        candidate = str(signal.get("candidate_id", "")).strip().upper()
        if not candidate:
            candidate = "|".join([str(signal.get("strategy", "STRATEGY_1")).strip().upper(), str(signal.get("symbol", "")).strip().upper(), str(signal.get("signal", "")).strip().upper(), str(signal.get("open_cross_level", "")).strip(), str(signal.get("pdh", "")).strip(), str(signal.get("pdl", "")).strip()])
        return ("CANDIDATE", candidate)

    def daily_limit_reached(self):
        return self.daily_pnl <= -float(DAILY_MAX_LOSS) or self.daily_pnl >= float(DAILY_PROFIT_TARGET)

    def cooldown_active(self):
        if self.cooldown_until is None:
            return False
        now = self._now().replace(tzinfo=None)
        if now >= self.cooldown_until:
            self.cooldown_until = None
            return False
        return True

    def _attach_trade_context(self, position, signal):
        fields = ("strategy", "strategy_name", "strategy_version", "candidate_id", "open_cross_level", "pdh", "pdl", "today_open", "today_low", "today_high", "market_direction", "stock_direction", "stock_today_direction", "setup_type", "trigger_close", "pdh_pdl_reached", "nifty500_universe", "priority_rank", "risk_per_share", "actual_risk", "position_value", "previous_day_close", "gap", "gap_percent", "gap_type")
        for field in fields:
            if field in signal:
                position[field] = signal[field]
        return position

    def _persist_closed_trade(self, trade):
        if not isinstance(trade, dict) or not trade.get("trade_id"):
            return False
        for attempt in range(3):
            try:
                if self.journal.log_trade(dict(trade)).get("saved", False):
                    return True
            except Exception as error:
                if attempt == 2:
                    print(f"Closed trade journal save failed for {trade.get('symbol', '')}: {type(error).__name__}: {error}")
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
        return False

    def _retry_closed_journal(self):
        ok = True
        for trade in list(self.paper_engine.closed_positions):
            if str(trade.get("exit_time", "")).strip() and str(trade.get("status", "")).upper() == "CLOSED":
                if not self._persist_closed_trade(trade):
                    ok = False
        return ok

    def process_signal(self, signal):
        if not isinstance(signal, dict):
            return
        entry_time = signal.get("entry_time")
        parsed = pd.to_datetime(entry_time, errors="coerce")
        if entry_time is None or pd.isna(parsed):
            return
        parsed = parsed.tz_localize(INDIA_TZ) if getattr(parsed, "tzinfo", None) is None else parsed.tz_convert(INDIA_TZ)
        if parsed.date() != self._now().date():
            return
        key = self.signal_key(signal)
        symbol = str(signal.get("symbol", "")).strip().upper()
        if not symbol or key in self.processed_signals:
            return
        if self.daily_limit_reached() or self.cooldown_active() or len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS or self.paper_engine.has_open_position(symbol):
            return
        risk_result = self.risk_engine.approve_trade(signal, available_capital=float(self.paper_engine.available_capital))
        row = dict(signal)
        row.update({"risk_per_share": risk_result.get("risk_per_share", ""), "actual_risk": risk_result.get("actual_risk", ""), "position_value": risk_result.get("position_value", "")})
        row["timestamp"] = signal.get("entry_time") or self._now().isoformat()
        row["approved"] = bool(risk_result.get("approved", False))
        reasons = risk_result.get("reasons", [])
        row["reason"] = "; ".join(map(str, reasons)) if isinstance(reasons, list) else str(reasons)
        try:
            self.journal.log_signal(row)
        except Exception as error:
            print("Signal journal save failed:", error)
        if not risk_result.get("approved", False):
            reasons_text = " ".join(str(x).upper() for x in risk_result.get("reasons", []))
            if "CAPITAL" not in reasons_text:
                self.processed_signals.add(key)
            return
        approved_trade = dict(signal)
        approved_trade.update(risk_result)
        approved_trade["approved"] = True
        try:
            result = self.paper_engine.open_trade(approved_trade)
        except Exception as error:
            print(f"Paper trade open failed for {symbol}: {type(error).__name__}: {error}")
            return
        if not result.get("opened", False):
            if "capital" not in str(result.get("reason", "")).lower():
                self.processed_signals.add(key)
            return
        position = self.paper_engine.open_positions.get(symbol)
        if position is None:
            return
        self._attach_trade_context(position, approved_trade)
        try:
            if not self.journal.log_trade(position.copy()).get("saved", False):
                self.paper_engine.open_positions.pop(symbol, None)
                print(f"Paper trade {symbol} rolled back because the OPEN trade journal could not be saved")
                return
        except Exception as error:
            print(f"Open trade journal save failed for {symbol}: {type(error).__name__}: {error}")
            return
        self.processed_signals.add(key)

    def _process_open_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            live = self.price_data.get_latest_live_price(symbol, max_age_seconds=3)
            closed = None
            if live is not None:
                closed = self.paper_engine.process_live_price(symbol, live.get("Close"), live.get("Datetime"))
            if closed is None:
                candle = self.price_data.get_latest_available_1m(symbol)
                if candle is not None:
                    closed = self.paper_engine.process_candle(symbol, candle)
            if closed is not None:
                self.daily_pnl = round(self.daily_pnl + float(closed.get("pnl", 0) or 0), 2)
                self._persist_closed_trade(closed)
                if str(closed.get("exit_reason", "")).upper() == "STOP_LOSS":
                    exit_dt = self._journal_ist(closed.get("exit_time"))
                    base = exit_dt.to_pydatetime() if pd.notna(exit_dt) else self._now()
                    self.cooldown_until = (base + timedelta(minutes=COOLDOWN_MINUTES)).replace(tzinfo=None)
        self._retry_closed_journal()
        self.missed_capital.monitor()

    def monitor_positions_once(self):
        """Fast execution loop: live LTP is checked independently of the scanner."""
        if self.current_time() >= SQUARE_OFF_TIME:
            return
        try:
            self._process_open_positions()
            self.strategy2.process_positions()
        except Exception as error:
            print(f"Fast position monitor error: {type(error).__name__}: {error}")

    def _position_monitor_loop(self):
        while self.running:
            try:
                now = self._now()
                if now.weekday() < 5 and TRADING_START <= now.strftime("%H:%M") < SQUARE_OFF_TIME:
                    self.monitor_positions_once()
            except Exception as error:
                print(f"Position monitor loop error: {type(error).__name__}: {error}")
            time.sleep(POSITION_MONITOR_SECONDS)

    def scan_for_entries(self):
        now = self.current_time()
        if now < TRADING_START or now > LAST_ENTRY_TIME:
            return
        if not self.daily_limit_reached() and not self.cooldown_active() and len(self.paper_engine.open_positions) < MAX_OPEN_POSITIONS:
            signals = self.scanner.scan() or []
            for signal in signals:
                if self.daily_limit_reached() or self.cooldown_active() or len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
                    break
                self.process_signal(signal)
        try:
            self.strategy2.scan()
        except Exception as error:
            print(f"Strategy 2 scan failed: {type(error).__name__}: {error}")

    def latest_1m_candle(self, symbol):
        try:
            return self.price_data.get_latest_available_1m(symbol)
        except Exception as error:
            print(symbol, "1-minute data error:", error)
            return None

    def _square_off_price(self, symbol, position):
        try:
            live = self.price_data.get_latest_live_price(symbol, max_age_seconds=3)
            if live is not None:
                return float(live["Close"]), live.get("Datetime") or self._now()
        except Exception as error:
            print(f"Live square-off price unavailable for {symbol}: {type(error).__name__}: {error}")
        try:
            candle = self.latest_1m_candle(symbol)
            if candle is not None:
                return float(candle.get("Close")), candle.get("Datetime") or self._now()
        except Exception as error:
            print(f"Latest 1m fallback unavailable for {symbol}: {type(error).__name__}: {error}")
        return None, None

    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            price, exit_time = self._square_off_price(symbol, self.paper_engine.open_positions.get(symbol, {}))
            if price is None:
                continue
            closed = self.paper_engine.close_position(symbol, price, exit_time, "SQUARE_OFF")
            if closed is not None:
                self.daily_pnl = round(self.daily_pnl + float(closed.get("pnl", 0) or 0), 2)
        self._retry_closed_journal()
        self.strategy2.square_off_all()
        self.square_off_done = (not bool(self.paper_engine.open_positions)) and not bool(self.strategy2.paper_engine.open_positions)

    def run_cycle(self):
        if self.current_time() >= SQUARE_OFF_TIME:
            if not self.square_off_done:
                self.square_off_all()
            return
        self.square_off_done = False
        self.scan_for_entries()
