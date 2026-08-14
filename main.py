"""Core paper-trading orchestration for the NIFTY 500 open-reversal strategy."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import (
    PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME,
    SQUARE_OFF_TIME, MAX_OPEN_POSITIONS, DAILY_MAX_LOSS,
    DAILY_PROFIT_TARGET, COOLDOWN_MINUTES, RISK_REWARD_RATIO,
)
from scanner.scanner_engine import ScannerEngine
from strategy.risk_engine import RiskEngine
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal import TradeJournal
from papertrade.missed_capital_tracker import MissedCapitalTracker

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class TradingBot:
    """Run one NIFTY 500 paper-trading session without live execution."""

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
        self.missed_capital = MissedCapitalTracker(self.journal, self.price_data)
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
            exits = pd.to_datetime(df["exit_time"], errors="coerce")
            if getattr(exits.dt, "tz", None) is None:
                dates = exits.dt.date
            else:
                dates = exits.dt.tz_convert(INDIA_TZ).dt.date
            mask = dates == self._now().date()
            if "status" in df.columns:
                mask &= df["status"].astype(str).str.upper().eq("CLOSED")
            pnl = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
            return round(float(pnl[mask].sum()), 2)
        except Exception as error:
            print("Daily P&L restore skipped:", error)
            return 0.0

    def _restore_cooldown(self):
        try:
            df = self.journal.get_trades()
            if df.empty or "exit_time" not in df.columns or "exit_reason" not in df.columns:
                return None
            closed = df[df.get("status", "").astype(str).str.upper().eq("CLOSED")].copy()
            closed = closed[closed["exit_reason"].astype(str).str.upper().eq("STOP_LOSS")]
            if closed.empty:
                return None
            times = pd.to_datetime(closed["exit_time"], errors="coerce")
            if getattr(times.dt, "tz", None) is None:
                times = times.dt.tz_localize(INDIA_TZ)
            else:
                times = times.dt.tz_convert(INDIA_TZ)
            times = times[times.dt.date == self._now().date()].dropna()
            if times.empty:
                return None
            end = times.max().to_pydatetime() + timedelta(minutes=COOLDOWN_MINUTES)
            return end.replace(tzinfo=None) if end > self._now() else None
        except Exception:
            return None

    def signal_key(self, signal):
        return (
            str(signal.get("symbol", "")).strip().upper(),
            str(signal.get("signal", "")).strip().upper(),
            str(signal.get("entry_time", "")),
            str(signal.get("open_cross_level", "")),
        )

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
            print("Signal journal save failed:", error)

    def _attach_trade_context(self, position, signal):
        fields = (
            "industry", "sector", "open_cross_level", "pdh", "pdl", "today_open",
            "today_low", "today_high", "market_direction", "sector_direction",
            "stock_direction", "stock_today_direction", "setup_type",
            "trigger_candle_open", "trigger_candle_close", "trigger_close",
            "pdh_pdl_reached", "liquidity_qualified", "nifty500_universe",
            "risk_per_share", "actual_risk", "position_value",
        )
        for field in fields:
            if field in signal:
                position[field] = signal[field]
        return position

    def _set_market_entry(self, signal):
        """Use the next available market price after the completed trigger candle."""
        side = str(signal.get("signal", "")).upper()
        stop = float(signal.get("stop_loss", 0) or 0)
        trigger_close = float(signal.get("trigger_candle_close", signal.get("entry", 0)) or 0)
        quote = self.price_data.get_latest_available_1m(str(signal.get("symbol", "")))
        if not quote:
            return False
        try:
            market_price = float(quote.get("Close"))
        except (TypeError, ValueError):
            return False
        if market_price <= 0:
            return False
        if side == "BUY" and stop >= market_price:
            return False
        if side == "SELL" and stop <= market_price:
            return False

        signal["trigger_entry_time"] = signal.get("entry_time")
        signal["trigger_close"] = trigger_close
        signal["market_entry_time"] = self._now().isoformat(timespec="seconds")
        signal["entry"] = round(market_price, 2)
        signal["entry_time"] = signal["market_entry_time"]
        reward_distance = abs(market_price - stop) * float(RISK_REWARD_RATIO)
        signal["target"] = round(market_price + reward_distance if side == "BUY" else market_price - reward_distance, 2)
        return True

    def process_signal(self, signal):
        if not isinstance(signal, dict):
            return
        symbol = str(signal.get("symbol", "")).strip().upper()
        if not symbol or not self._set_market_entry(signal):
            return
        key = self.signal_key(signal)
        if key in self.processed_signals:
            return
        if self.daily_limit_reached() or self.cooldown_active():
            return
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS or self.paper_engine.has_open_position(symbol):
            return

        risk_result = self.risk_engine.approve_trade(signal)
        self.log_signal(signal, risk_result)
        if not risk_result.get("approved", False):
            self.processed_signals.add(key)
            return

        approved_trade = dict(signal)
        approved_trade.update(risk_result)
        approved_trade["approved"] = True
        result = self.paper_engine.open_trade(approved_trade)
        if not result.get("opened", False):
            if str(result.get("reason", "")) == "Insufficient available capital":
                self.missed_capital.record(signal, risk_result, result["reason"])
            try:
                count = self.risk_engine.get_trade_count(symbol)
                if count > 0:
                    self.risk_engine.trade_counts[symbol] = count - 1
            except Exception:
                pass
            self.processed_signals.add(key)
            return

        self.processed_signals.add(key)
        position = self.paper_engine.open_positions.get(symbol)
        if position is None:
            return
        self._attach_trade_context(position, approved_trade)
        self.journal.log_trade(position.copy())

    def _process_open_positions(self):
        for symbol in list(self.paper_engine.open_positions):
            candle = self.latest_1m_candle(symbol)
            if candle is None:
                continue
            closed = self.paper_engine.process_candle(symbol, candle)
            if closed is not None:
                self.journal.log_trade(closed)
                self.daily_pnl = self._restore_daily_pnl()

    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            quote = self.price_data.get_latest_available_1m(symbol)
            if not quote:
                continue
            price = quote.get("Close")
            stamp = quote.get("Datetime") or self._now().replace(second=0, microsecond=0)
            closed = self.paper_engine.close_position(symbol, price, stamp, "SQUARE_OFF")
            if closed is not None:
                self.journal.log_trade(closed)
        self.daily_pnl = self._restore_daily_pnl()
        self.square_off_done = True

    def scan_for_entries(self):
        now = self.current_time()
        if now < TRADING_START or now > LAST_ENTRY_TIME:
            return
        if self.daily_limit_reached() or self.cooldown_active():
            return
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
            return
        signals = self.scanner.scan() or []
        for signal in signals:
            if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
                break
            self.process_signal(signal)

    def latest_1m_candle(self, symbol):
        try:
            df = self.price_data.today_only(self.price_data.get_1m(symbol))
        except Exception as error:
            print(symbol, "1-minute data error:", error)
            return None
        if df is None or df.empty:
            return None
        return df.iloc[-1].to_dict()

    def run_cycle(self):
        """One worker cycle: manage open positions, then look for new entries."""
        now = self.current_time()
        if now >= SQUARE_OFF_TIME:
            if not self.square_off_done:
                self.square_off_all()
            return
        self.square_off_done = False
        self._process_open_positions()
        self.scan_for_entries()
