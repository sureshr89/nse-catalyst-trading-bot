"""Runtime for Strategy 2: gap-up extension reversal SELL.

Strategy 2 has an isolated ₹2.5 lakh paper capital pool and journal so it cannot
consume Strategy 1 capital or positions.
"""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json

from config.settings import TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME, MAX_OPEN_POSITIONS, DAILY_MAX_LOSS, DAILY_PROFIT_TARGET, COOLDOWN_MINUTES
from strategy.gap_extension_reversal_engine import GapExtensionReversalEngine
from strategy.risk_engine import RiskEngine
from papertrade.strategy2_paper_engine import Strategy2PaperTradeEngine
from papertrade.trade_journal_clean import TradeJournal
from news.sentiment import analyze_yahoo_news, news_allows_trade

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class Strategy2Runtime:
    def __init__(self, scanner):
        self.scanner = scanner
        self.strategy = GapExtensionReversalEngine(TRADING_START, LAST_ENTRY_TIME, 1.25)
        self.risk_engine = RiskEngine()
        self.paper_engine = Strategy2PaperTradeEngine()
        self.journal = TradeJournal("outputs/strategy2_trades.csv", "outputs/strategy2_signals.csv")
        self.processed = set()
        self.daily_pnl = 0.0
        self.cooldown_until = None
        self.last_signals = []
        self.diagnostics = {"strategy": "STRATEGY_2_GAP_UP_EXTENSION_REVERSAL", "signals": 0, "candidates": 0, "qualified": 0, "rejections": {}}

    @staticmethod
    def _now():
        return datetime.now(INDIA_TZ)

    def _write_diagnostics(self):
        payload = dict(self.diagnostics)
        payload["timestamp"] = self._now().isoformat(timespec="seconds")
        payload["open_positions"] = len(self.paper_engine.open_positions)
        payload["available_capital"] = self.paper_engine.available_capital
        payload["used_capital"] = self.paper_engine.used_capital
        payload["daily_pnl"] = self.daily_pnl
        path = Path("outputs/strategy2_diagnostics.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _news_gate(self, signal):
        symbol = signal["symbol"]
        analysis = analyze_yahoo_news(symbol)
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
        signal["candidate_id"] = candidate_id
        signal["priority_rank"] = rank
        signal["candidate_state"] = "QUALIFIED"
        signal["nifty500_universe"] = True
        if candidate_id in self.processed:
            return False
        if self.daily_pnl <= -DAILY_MAX_LOSS or self.daily_pnl >= DAILY_PROFIT_TARGET:
            self.diagnostics["rejections"]["daily_limit"] = self.diagnostics["rejections"].get("daily_limit", 0) + 1
            return False
        if self.cooldown_until and self._now().replace(tzinfo=None) < self.cooldown_until:
            self.diagnostics["rejections"]["cooldown"] = self.diagnostics["rejections"].get("cooldown", 0) + 1
            return False
        if len(self.paper_engine.open_positions) >= MAX_OPEN_POSITIONS:
            self.diagnostics["rejections"]["position_limit"] = self.diagnostics["rejections"].get("position_limit", 0) + 1
            return False
        if not self._news_gate(signal):
            self.journal.log_signal({**signal, "approved": False, "reason": "NEWS_REJECTED"})
            self.processed.add(candidate_id)
            return False
        risk = self.risk_engine.approve_trade(signal, available_capital=self.paper_engine.available_capital)
        self.journal.log_signal({**signal, **risk, "approved": bool(risk.get("approved")), "reason": "; ".join(map(str, risk.get("reasons", [])))} )
        if not risk.get("approved"):
            self.diagnostics["rejections"]["risk"] = self.diagnostics["rejections"].get("risk", 0) + 1
            if "CAPITAL" not in " ".join(map(str, risk.get("reasons", []))).upper():
                self.processed.add(candidate_id)
            return False
        trade = dict(signal)
        trade.update(risk)
        trade["approved"] = True
        result = self.paper_engine.open_trade(trade)
        if not result.get("opened"):
            self.diagnostics["rejections"]["execution"] = self.diagnostics["rejections"].get("execution", 0) + 1
            if "capital" not in str(result.get("reason", "")).lower():
                self.processed.add(candidate_id)
            return False
        position = result.get("position")
        if position:
            self.journal.log_trade(position)
        self.processed.add(candidate_id)
        return True

    def scan(self):
        if self._now().strftime("%H:%M") < TRADING_START or self._now().strftime("%H:%M") > LAST_ENTRY_TIME:
            return []
        candidates = self.scanner.opening_candidates
        data = self.scanner.universe_market_data
        nifty_change = self.scanner._nifty_change
        if candidates is None or candidates.empty:
            candidates = self.scanner.prepare_opening_candidates()
            data = self.scanner.universe_market_data
        rows = []
        for _, row in candidates.iterrows():
            # Strategy 2 is only for genuine gap-ups above PDH.
            if str(row.get("OpeningSetup", "")) != "OPEN_ABOVE_PDH":
                continue
            symbol = str(row["Symbol"]).upper()
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

    def run_cycle(self):
        self.process_positions()
        return self.scan()

    def square_off_all(self):
        for symbol in list(self.paper_engine.open_positions):
            candle = self.scanner.price_data.get_latest_available_1m(symbol)
            if candle is None:
                continue
            close = float(candle["Close"])
            closed = self.paper_engine.close_position(symbol, close, candle["Datetime"], "SQUARE_OFF")
            if closed:
                self.daily_pnl = round(self.daily_pnl + float(closed.get("pnl", 0) or 0), 2)
                self.journal.log_trade(closed)
        self._write_diagnostics()
