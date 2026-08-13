"""Core paper-trading bot for the NIFTY 100 Gap-Failure + Open-Reclaim strategy.

This module contains execution orchestration only. Strategy decisions come from
ScannerEngine, risk approval comes from RiskEngine, and simulated execution is
handled by PaperTradeEngine. All time comparisons are IST-safe.
"""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import (
    PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME,
    SQUARE_OFF_TIME, SCAN_INTERVAL_SECONDS, MAX_OPEN_POSITIONS,
    DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES,
)
from scanner.scanner_engine import ScannerEngine
from strategy.risk_engine import RiskEngine
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal import TradeJournal

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class TradingBot:
    """Orchestrate one paper-trading session without changing strategy rules."""

    def __init__(self):
        if LIVE_TRADING:
            raise RuntimeError("LIVE_TRADING must be False. This bot is paper trading only.")
        if not PAPER_TRADING:
            raise RuntimeError("PAPER_TRADING must be True.")
        self.scanner = ScannerEngine()
        self.risk_engine = RiskEngine()
        self.price_data = PriceData()
        self.paper_engine = PaperTradeEngine()
        self.journal = TradeJournal()
        self.running = True
        self.processed_signals = set()
        self.daily_pnl = self._restore_daily_pnl()
        self.cooldown_until = self._restore_cooldown()
        self.square_off_done = False

    @staticmethod
    def _now():
        return datetime.now(INDIA_TZ)

    def current_time(self):
        return self._now().strftime("%H:%M")

    def _restore_daily_pnl(self):
        try:
            df = self.journal.get_trades()
            if df.empty or "pnl" not in df.columns or "exit_time" not in df.columns:
                return 0.0
            raw_exits = pd.to_datetime(df["exit_time"], errors="coerce")
            today = self._now().date()
            pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
            if getattr(raw_exits.dt, "tz", None) is None:
                dates = raw_exits.dt.date
            else:
                dates = raw_exits.dt.tz_convert(INDIA_TZ).dt.date
            closed_mask = dates == today
            if "status" in df.columns:
                closed_mask &= df["status"].astype(str).str.upper().eq("CLOSED")
            return round(float(pnl[closed_mask].sum()), 2)
        except Exception as error:
            print(f"Daily P&L restore skipped: {type(error).__name__}: {error}")
            return 0.0

    def _restore_cooldown(self):
        try:
            df = self.journal.get_trades()
            if df.empty or "exit_time" not in df.columns or "exit_reason" not in df.columns:
                return None
            today = self._now().date()
            closed = df.copy()
            if "status" in closed.columns:
                closed = closed[closed["status"].astype(str).str.upper() == "CLOSED"]
            closed = closed[closed["exit_reason"].astype(str).str.upper() == "STOP_LOSS"]
            if closed.empty:
                return None
            times = pd.to_datetime(closed["exit_time"], errors="coerce")
            if getattr(times.dt, "tz", None) is None:
                times = times.dt.tz_localize(INDIA_TZ)
            else:
                times = times.dt.tz_convert(INDIA_TZ)
            times = times[times.dt.date == today].dropna()
            if times.empty:
                return None
            cooldown_end = times.max().to_pydatetime() + timedelta(minutes=COOLDOWN_MINUTES)
            if cooldown_end <= self._now():
                return None
            return cooldown_end.replace(tzinfo=None)
        except Exception as error:
            print(f"Cooldown restore skipped: {type(error).__name__}: {error}")
            return None

    def signal_key(self, signal):
        return (
            str(signal.get("symbol", "")).strip().upper(),
            str(signal.get("signal", "")).strip().upper(),
            str(signal.get("entry_time", "")),
            str(signal.get("breakout_level", "")),
        )

    def log_signal(self, signal, risk_result):
        row = dict(signal)
        row.update({
            "risk_per_share": risk_result.get("risk_per_share", ""),
            "actual_risk": risk_result.get("actual_risk", ""),
            "position_value": risk_result.get("position_value", ""),
        })
        row["timestamp"] = signal.get("entry_time") or self._now().isoformat()
        row["approved"] = bool(risk_result.get("approved", False))
        reasons = risk_result.get("reasons", [])
        row["reason"] = "; ".join(map(str, reasons)) if isinstance(reasons, list) else str(reasons)
        try:
            self.journal.log_signal(row)
        except Exception as error:
            print(f"Signal journal save failed: {type(error).__name__}: {error}")

    def daily_limit_reached(self):
        if self.daily_pnl <= -float(DAILY_MAX_LOSS):
            print("Daily max loss reached.")
            return True
        if self.daily_pnl >= float(DAILY_PROFIT_TARGET):
            print("Daily profit target reached.")
            return True
        return False

    def cooldown_active(self):
        if self.cooldown_until is None:
            return False
        now = self._now().replace(tzinfo=None)
        if now >= self.cooldown_until:
            self.cooldown_until = None
            return False
        return True

    def _attach_trade_context(self, position, signal):
        context_fields = (
            "stock", "industry", "sector", "buy_sell", "breakout_level", "pdc",
            "today_open", "today_low", "today_high", "market_direction",
            "nifty100_direction", "industry_direction", "sector_direction",
            "stock_direction", "stock_today_direction", "previous_day_aligned",
            "previous_day_direction", "setup_type", "entry_candle_open",
            "entry_candle_close", "risk_per_share", "actual_risk", "position_value",
        )
        for field in context_fields:
            if field in signal:
                position[field] = signal[field]
        return position

    def process_signal(self, signal):
        if not isinstance(signal, dict):
            return
        symbol = str(signal.get("symbol", "")).strip().upper()
        if not symbol:
            return
        key = self.signal_key(signal)
        if key in self.processed_signals:
            return
        if self.daily_limit_reached() or self.cooldown_active():
            return
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
            return
        if self.paper_engine.has_open_position(symbol):
            return

        risk_result = self.risk_engine.approve_trade(signal)
        self.log_signal(signal, risk_result)
        if not risk_result.get("approved", False):
            self.processed_signals.add(key)
            print("Risk rejected", symbol, risk_result.get("reasons", []))
            return

        approved_trade = dict(signal)
        approved_trade.update(risk_result)
        approved_trade["approved"] = True
        open_result = self.paper_engine.open_trade(approved_trade)
        if not open_result.get("opened", False):
            try:
                count = self.risk_engine.get_trade_count(symbol)
                if count > 0:
                    self.risk_engine.trade_counts[symbol] = count - 1
            except Exception:
                pass
            print("Paper trade not opened:", symbol, open_result.get("reason", ""))
            return

        self.processed_signals.add(key)
        live_position = self.paper_engine.open_positions.get(symbol)
        if live_position is None:
            print("Paper trade opened but live position is missing:", symbol)
            return
        self._attach_trade_context(live_position, approved_trade)
        live_position["status"] = "OPEN"
        saved = self.journal.log_trade(live_position.copy())
        print(
            "PAPER OPENED:", symbol, approved_trade.get("signal"),
            "entry=", live_position.get("entry"), "SL=", live_position.get("stop_loss"),
            "target=", live_position.get("target"), "qty=", live_position.get("quantity"),
            "risk=", live_position.get("actual_risk"), "R:R=", live_position.get("rr"),
            "journal=", saved.get("saved", False),
        )

    def scan_for_entries(self):
        now = self.current_time()
        if now < TRADING_START or now > LAST_ENTRY_TIME:
            return
        if self.daily_limit_reached() or self.cooldown_active():
            return
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
            return
        try:
            signals = self.scanner.scan() or []
        except Exception as error:
            print(f"Scanner error: {type(error).__name__}: {error}")
            raise
        if not isinstance(signals, list):
            raise TypeError("Scanner returned unexpected data; expected a list of signals")
        for signal in signals:
            if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
                break
            self.process_signal(signal)

    def latest_1m_candle(self, symbol):
        """Return the latest completed 1-minute candle for exit monitoring."""
        try:
            df = self.price_data.get_1m(symbol)
        except Exception as error:
            print(symbol, "1-minute data error:", error)
            return None
        if df is None or df.empty:
            return None
        try:
            today_df = self.price_data.today_only(df)
            if today_df is not None and not today_df.empty:
                df = today_df
        except Exception as error:
            print(symbol, "today filter warning:", error)
        if df is None or df.empty:
            return None

        frame = df.copy()
        try:
            if "Datetime" in frame.columns:
                timestamps = pd.to_datetime(frame["Datetime"], errors="coerce")
                if timestamps.dt.tz is None:
                    timestamps = timestamps.dt.tz_localize(INDIA_TZ)
                else:
                    timestamps = timestamps.dt.tz_convert(INDIA_TZ)
                frame = frame[timestamps < self._now().replace(second=0, microsecond=0)].copy()
            else:
                timestamps = pd.to_datetime(frame.index, errors="coerce")
                if timestamps.tz is None:
                    timestamps = timestamps.tz_localize(INDIA_TZ)
                else:
                    timestamps = timestamps.tz_convert(INDIA_TZ)
                frame = frame[timestamps < self._now().replace(second=0, microsecond=0)].copy()
        except Exception:
            if len(frame) > 1:
                frame = frame.iloc[:-1]
        if frame.empty:
            return None
        row = frame.iloc[-1]
        candle = row.to_dict()
        candle.setdefault("Datetime", row.get("Datetime", row.name))
        return candle

    def monitor_position(self, symbol):
        candle = self.latest_1m_candle(symbol)
        if candle is None:
            return
        closed_trade = self.paper_engine.process_candle(symbol, candle)
        if closed_trade is None:
            return
        pnl = float(closed_trade.get("pnl", 0) or 0)
        self.daily_pnl = round(self.daily_pnl + pnl, 2)
        if str(closed_trade.get("exit_reason", "")).upper() == "STOP_LOSS":
            self.cooldown_until = self._now().replace(tzinfo=None) + timedelta(minutes=COOLDOWN_MINUTES)
        saved = self.journal.log_trade(closed_trade)
        print(
            "PAPER CLOSED:", symbol, "reason=", closed_trade.get("exit_reason"),
            "exit=", closed_trade.get("exit_price"), "P&L=", pnl,
            "journal=", saved.get("saved", False),
        )

    def monitor_open_positions(self):
        for symbol in list(self.paper_engine.open_positions.keys()):
            self.monitor_position(symbol)

    def force_square_off(self):
        """Close every remaining position at the latest completed price."""
        symbols = list(self.paper_engine.open_positions.keys())
        if not symbols:
            return
        for symbol in symbols:
            if self.paper_engine.open_positions.get(symbol) is None:
                continue
            candle = self.latest_1m_candle(symbol)
            if candle is None:
                print(symbol, "square-off skipped: no completed 1-minute candle")
                continue
            exit_price = candle.get("Close", candle.get("close"))
            exit_time = candle.get("Datetime", candle.get("datetime")) or self._now().replace(tzinfo=None)
            try:
                exit_price = float(exit_price)
            except (TypeError, ValueError):
                print(symbol, "square-off skipped: invalid completed close")
                continue
            closed_trade = self.paper_engine.close_position(symbol, exit_price, exit_time, "SQUARE_OFF")
            if closed_trade is None:
                continue
            pnl = float(closed_trade.get("pnl", 0) or 0)
            self.daily_pnl = round(self.daily_pnl + pnl, 2)
            saved = self.journal.log_trade(closed_trade)
            print("SQUARE OFF:", symbol, "exit=", exit_price, "P&L=", pnl, "journal=", saved.get("saved", False))

    def display_status(self):
        session = self.paper_engine.summary()
        history = self.journal.summary()
        print(
            "STATUS", self.current_time(), "open=", session.get("open_positions", 0),
            "session_pnl=", session.get("total_pnl", 0), "daily_pnl=", round(self.daily_pnl, 2),
            "journal_trades=", history.get("total_trades", 0), "journal_pnl=", history.get("total_pnl", 0),
        )

    def run_cycle(self):
        now = self.current_time()
        if now >= SQUARE_OFF_TIME:
            if not self.square_off_done:
                self.force_square_off()
                self.square_off_done = True
            self.display_status()
            return
        self.monitor_open_positions()
        if self.current_time() < SQUARE_OFF_TIME:
            self.scan_for_entries()
        self.display_status()

    def run(self):
        print("=" * 90)
        print("NSE CATALYST — NIFTY 100 GAP-FAILURE + OPEN-RECLAIM PAPER BOT")
        print("Strategy: pure price action | Paper: ON | Live: OFF")
        print(f"Entry: {TRADING_START}-{LAST_ENTRY_TIME} IST | Square-off: {SQUARE_OFF_TIME} IST | Scan: {SCAN_INTERVAL_SECONDS}s")
        print("=" * 90)
        try:
            while self.running:
                self.run_cycle()
                if self.current_time() >= SQUARE_OFF_TIME and not self.paper_engine.open_positions:
                    break
                time.sleep(max(1, int(SCAN_INTERVAL_SECONDS)))
        except KeyboardInterrupt:
            print("Bot stopped manually.")
        except Exception as error:
            print(f"FATAL BOT ERROR: {type(error).__name__}: {error}")
            raise
        finally:
            print("FINAL JOURNAL SUMMARY:", self.journal.summary())


if __name__ == "__main__":
    TradingBot().run()
