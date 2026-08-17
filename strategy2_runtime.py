"""Runtime for Strategy 2: gap-up extension reversal SELL.

Strategy 2 has an isolated ₹2.5 lakh paper capital pool, journal, risk state,
and session recovery so it cannot consume or count against Strategy 1.
"""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd

from config.settings import TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MAX_OPEN_POSITIONS, DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES
from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine
from strategy.strategy2_risk_engine import Strategy2RiskEngine
from papertrade.strategy2_paper_engine import Strategy2PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from news.sentiment import analyze_yahoo_news, news_allows_trade

INDIA_TZ = ZoneInfo("Asia/Kolkata")
STRATEGY2_TRADES = Path("outputs/strategy2_trades.csv")


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
        self.diagnostics = {"strategy": "STRATEGY_2_GAP_UP_EXTENSION_REVERSAL", "signals": 0, "candidates": 0, "qualified": 0, "rejections": {}}
        self._restore_session()
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
            if getattr(parsed, "tzinfo", None) is None:
                parsed = parsed.tz_localize(INDIA_TZ)
            else:
                parsed = parsed.tz_convert(INDIA_TZ)
            return parsed.date()
        except Exception:
            return None

    def _restore_session(self):
        today = self._now().date()
        try:
            df = self.journal.get_trades()
            if df.empty or not {"status", "exit_time", "pnl"}.issubset(df.columns):
                return
            closed = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
            if closed.empty:
                return
            dates = closed["exit_time"].map(self._date_ist)
            pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
            self.daily_pnl = round(float(pnl[dates.eq(today)].sum()), 2)
            if "exit_reason" not in closed.columns:
                return
            stop_rows = closed.loc[dates.eq(today) & closed["exit_reason"].astype(str).str.upper().eq("STOP_LOSS")]
            if stop_rows.empty:
                return
            last_stop = pd.to_datetime(stop_rows["exit_time"], errors="coerce").dropna().max()
            if pd.isna(last_stop):
                return
            if getattr(last_stop, "tzinfo", None) is None:
                last_stop = last_stop.tz_localize(INDIA_TZ)
            else:
                last_stop = last_stop.tz_convert(INDIA_TZ)
            end = last_stop.to_pydatetime() + timedelta(minutes=COOLDOWN_MINUTES)
            if end > self._now():
                self.cooldown_until = end.replace(tzinfo=None)
        except Exception as error:
            print(f"Strategy 2 session restore skipped: {type(error).__name__}: {error}")

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

    def _news_gate(self, signal):
        analysis = analyze_yahoo_news(signal["symbol"])
        signal.update({
            "news_sentiment": analysis.get("sentiment", "NEUTRAL"),
            "news_confidence": analysis.get("confidence", 0.0),
            "news_headline": analysis.get("headline", ""),
            "news_reason": analysis.get("reason", ""),
            "news_source": analysis.get("source", "Yahoo Finance"),
            "news_checked_at": self._now().isoformat(),
        })
        return news_allows_trade("SELL", analysis)

    def _open_signal(self, signal, rank):
        candidate_id = f"S2|{self._now().date().isoformat()}|{signal['symbol']}|{signal['trigger_time']}"
        signal.update({"candidate_id": candidate_id, "entry_time": signal["trigger_time"], "open_cross_level": signal["today_open"], "today_high": signal["stop_loss"], "priority_rank": rank, "candidate_state": "QUALIFIED", "nifty500_universe": True, "pdh_pdl_reached": False})
        if candidate_id in self.processed:
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
        if not self._news_gate(signal):
            self.journal.log_signal({**signal, "approved": False, "reason": "NEWS_REJECTED"})
            self._reject("news_rejected")
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
            candidates = self.scanner.prepare_opening_candidates()
            data = self.scanner.universe_market_data
        rows = []
        for _, row in candidates.iterrows():
            if str(row.get("OpeningSetup", "")) != "OPEN_ABOVE_PDH":
                continue
            symbol = str(row.get("Symbol", "")).upper().strip()
            if not symbol:
                continue
            stock_data = data.get(symbol)
            if stock_data is None or stock_data.empty:
                continue
            signal = self.strategy.evaluate(symbol, stock_data, row["TodayOpen"], row["PDH"], row["PreviousDayClose"], nifty_change)
            if signal:
                signal["gap_percent"] = float(row.get("GapPercentFromPreviousClose", signal.get("gap_percent", 0.0)))
                rows.append(signal)
        rows.sort(key=lambda x: abs(float(x.get("gap_percent", 0.0))), reverse=True)
        self.diagnostics["candidates"] = int(len(candidates))
        self.diagnostics["qualified"] = len(rows)
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
