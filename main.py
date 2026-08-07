import time
from datetime import datetime

from config.settings import (
    PAPER_TRADING,
    LIVE_TRADING,
    TRADING_START,
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    SCAN_INTERVAL_SECONDS,
    MAX_OPEN_POSITIONS,
    DAILY_MAX_LOSS,
    DAILY_PROFIT_TARGET,
)

from scanner.scanner_engine import ScannerEngine
from strategy.risk_engine import RiskEngine
from market.price_data import PriceData
from papertrade.paper_trade_engine import PaperTradeEngine
from papertrade.trade_journal import TradeJournal


class TradingBot:

    def __init__(self):

        # ========================================================
        # SAFETY
        # ========================================================

        if LIVE_TRADING:
            raise RuntimeError(
                "LIVE_TRADING must be False. "
                "This main.py is for paper trading only."
            )

        if not PAPER_TRADING:
            raise RuntimeError(
                "PAPER_TRADING must be True."
            )

        # ========================================================
        # ENGINES
        # ========================================================

        self.scanner = ScannerEngine()

        self.risk_engine = RiskEngine()

        self.price_data = PriceData()

        self.paper_engine = PaperTradeEngine()

        self.journal = TradeJournal()

        # ========================================================
        # STATE
        # ========================================================

        self.running = True

        # Prevent processing exactly the same scanner signal
        # repeatedly.

        self.processed_signals = set()
        self.daily_pnl = 0.0
        self.cooldown_until = None

    # ============================================================
    # CURRENT TIME
    # ============================================================

    def current_time(self):

        return datetime.now().strftime("%H:%M")

    # ============================================================
    # SIGNAL KEY
    # ============================================================

    def signal_key(self, signal):

        symbol = str(
            signal.get("symbol", "")
        ).strip().upper()

        side = str(
            signal.get("signal", "")
        ).strip().upper()

        entry_time = str(
            signal.get("entry_time", "")
        )

        breakout_level = str(
            signal.get("breakout_level", "")
        )

        return (
            symbol,
            side,
            entry_time,
            breakout_level,
        )

    # ============================================================
    # SAVE SIGNAL
    # ============================================================

    def log_signal(self, signal, risk_result):

        journal_signal = dict(signal)

        journal_signal["timestamp"] = (
            signal.get(
                "entry_time",
                datetime.now()
            )
        )

        journal_signal["approved"] = (
            risk_result.get(
                "approved",
                False
            )
        )

        reasons = risk_result.get(
            "reasons",
            []
        )

        if isinstance(reasons, list):

            reason_text = "; ".join(
                str(reason)
                for reason in reasons
            )

        else:

            reason_text = str(reasons)

        journal_signal["reason"] = (
            reason_text
        )

        self.journal.log_signal(
            journal_signal
        )

    # ============================================================
    # PROCESS ONE SCANNER SIGNAL
    # ============================================================

    def process_signal(self, signal):

        if not isinstance(signal, dict):
            return

        symbol = str(
            signal.get("symbol", "")
        ).strip().upper()

        if not symbol:
            return

        key = self.signal_key(signal)

        # Do not process exact same signal twice.

        if key in self.processed_signals:
            return

        self.processed_signals.add(key)

        print()
        print("-" * 100)
        print(
            "PROCESSING SIGNAL :",
            symbol,
            signal.get("signal")
        )
        print("-" * 100)

        # --------------------------------------------------------
        # DAILY LIMIT CHECKS
        # --------------------------------------------------------

        if self.daily_pnl <= -DAILY_MAX_LOSS:
            print(
                "Daily max loss reached. Skipping new trades."
            )
            return

        if self.daily_pnl >= DAILY_PROFIT_TARGET:
            print(
                "Daily profit target reached. Skipping new trades."
            )
            return

        # --------------------------------------------------------
        # EXISTING POSITION CHECK
        # --------------------------------------------------------

        if self.paper_engine.has_open_position(
            symbol
        ):

            print(
                symbol,
                "already has an open position."
            )

            return

        # --------------------------------------------------------
        # RISK APPROVAL
        # --------------------------------------------------------

        risk_result = (
            self.risk_engine.approve_trade(
                signal
            )
        )

        # Save approved and rejected signals.

        self.log_signal(
            signal,
            risk_result
        )

        approved = risk_result.get(
            "approved",
            False
        )

        print(
            "Risk Approved     :",
            approved
        )

        if not approved:

            print(
                "Risk Rejection   :",
                risk_result.get(
                    "reasons",
                    []
                )
            )

            return

        # --------------------------------------------------------
        # COMBINE SCANNER + RISK INFORMATION
        # --------------------------------------------------------

        approved_trade = dict(signal)

        approved_trade.update(
            risk_result
        )

        approved_trade["approved"] = True

        # --------------------------------------------------------
        # OPEN PAPER POSITION
        # --------------------------------------------------------

        open_result = (
            self.paper_engine.open_trade(
                approved_trade
            )
        )

        if not open_result.get(
            "opened",
            False
        ):

            print(
                "Paper Trade      : NOT OPENED"
            )

            print(
                "Reason           :",
                open_result.get(
                    "reason",
                    ""
                )
            )

            return

        position = open_result[
            "position"
        ]

        print(
            "Paper Trade       : OPENED"
        )

        print(
            "Trade ID          :",
            position["trade_id"]
        )

        print(
            "Symbol            :",
            position["symbol"]
        )

        print(
            "Signal            :",
            position["signal"]
        )

        print(
            "Entry             :",
            position["entry"]
        )

        print(
            "Stop Loss         :",
            position["stop_loss"]
        )

        print(
            "Target            :",
            position["target"]
        )

        print(
            "Quantity          :",
            position["quantity"]
        )

    # ============================================================
    # SCAN FOR NEW ENTRIES
    # ============================================================

    def scan_for_entries(self):

        now = self.current_time()

        if now < TRADING_START:

            print(
                "Waiting for trading start:",
                TRADING_START
            )

            return

        if now > LAST_ENTRY_TIME:

            print(
                "New-entry window closed."
            )

            return

        signals = self.scanner.scan()

        if signals is None:
            signals = []

        if not isinstance(signals, list):

            print(
                "WARNING: Scanner returned "
                "unexpected data."
            )

            return

        for signal in signals:

            self.process_signal(signal)

    # ============================================================
    # GET LATEST 1-MINUTE CANDLE
    # ============================================================

    def latest_1m_candle(self, symbol):

        try:

            df = self.price_data.get_1m(
                symbol
            )

        except Exception as error:

            print(
                symbol,
                "1-minute data error:",
                error
            )

            return None

        if df is None or df.empty:
            return None

        # Use today's data if possible.

        try:

            today_df = (
                self.price_data.today_only(
                    df
                )
            )

            if (
                today_df is not None
                and
                not today_df.empty
            ):

                df = today_df

        except Exception:
            pass

        if df.empty:
            return None

        row = df.iloc[-1]

        try:

            candle = row.to_dict()

        except Exception:
            return None

        # PriceData normally has Datetime as a column.
        # If not, use dataframe index.

        if (
            "Datetime" not in candle
            or candle.get("Datetime") is None
        ):

            candle["Datetime"] = row.name

        return candle

    # ============================================================
    # MONITOR ONE POSITION
    # ============================================================

    def monitor_position(self, symbol):

        candle = self.latest_1m_candle(
            symbol
        )

        if candle is None:

            print(
                symbol,
                ": no current 1-minute candle."
            )

            return

        closed_trade = (
            self.paper_engine.process_candle(
                symbol,
                candle
            )
        )

        if closed_trade is None:
            return

        print()
        print("=" * 100)
        print("PAPER TRADE CLOSED")
        print("=" * 100)

        print(
            "Trade ID          :",
            closed_trade.get(
                "trade_id"
            )
        )

        print(
            "Symbol            :",
            closed_trade.get(
                "symbol"
            )
        )

        print(
            "Exit Reason       :",
            closed_trade.get(
                "exit_reason"
            )
        )

        print(
            "Exit Price        :",
            closed_trade.get(
                "exit_price"
            )
        )

        print(
            "P&L               :",
            closed_trade.get(
                "pnl"
            )
        )

        self.daily_pnl += float(
            closed_trade.get("pnl", 0)
        )

        # --------------------------------------------------------
        # SAVE CLOSED TRADE
        # --------------------------------------------------------

        save_result = (
            self.journal.log_trade(
                closed_trade
            )
        )

        print(
            "Journal Saved     :",
            save_result.get(
                "saved",
                False
            )
        )

        print("=" * 100)

    # ============================================================
    # MONITOR ALL OPEN POSITIONS
    # ============================================================

    def monitor_open_positions(self):

        symbols = list(
            self.paper_engine
            .open_positions
            .keys()
        )

        if not symbols:
            return

        print()

        print(
            "Monitoring positions:",
            ", ".join(symbols)
        )

        for symbol in symbols:

            self.monitor_position(
                symbol
            )

    # ============================================================
    # STATUS
    # ============================================================

    def display_status(self):

        session = (
            self.paper_engine.summary()
        )

        history = (
            self.journal.summary()
        )

        print()
        print("-" * 100)
        print("BOT STATUS")
        print("-" * 100)

        print(
            "Time              :",
            self.current_time()
        )

        print(
            "Open Positions    :",
            session[
                "open_positions"
            ]
        )

        print(
            "Session Closed    :",
            session[
                "closed_positions"
            ]
        )

        print(
            "Session P&L       :",
            session[
                "total_pnl"
            ]
        )

        print("Available Capital :", session["available_capital"])
        print("Used Capital      :", session["used_capital"])
        print("Daily P&L         :", round(self.daily_pnl, 2))

        print(
            "Journal Trades    :",
            history[
                "total_trades"
            ]
        )

        print(
            "Journal P&L       :",
            history[
                "total_pnl"
            ]
        )

        print("-" * 100)

    # ============================================================
    # ONE COMPLETE BOT CYCLE
    # ============================================================

    def run_cycle(self):

        now = self.current_time()

        print()
        print("=" * 100)

        print(
            "BOT CYCLE :",
            now
        )

        print("=" * 100)

        # Always manage existing trades first.

        self.monitor_open_positions()

        # --------------------------------------------------------
        # 15:00 OR LATER
        # --------------------------------------------------------

        if now >= SQUARE_OFF_TIME:

            print(
                "Square-off time reached."
            )

            # Run monitoring once more.
            # PaperTradeEngine will square off using
            # the latest 15:00-or-later candle.

            self.monitor_open_positions()

            self.display_status()

            return

        # --------------------------------------------------------
        # NEW ENTRIES
        # --------------------------------------------------------

        self.scan_for_entries()

        self.display_status()

    # ============================================================
    # RUN BOT
    # ============================================================

    def run(self):

        print("=" * 100)

        print(
            "NIFTY LARGEMIDCAP 250 "
            "PULLBACK BREAKOUT PAPER BOT"
        )

        print("=" * 100)

        print(
            "Paper Trading     :",
            PAPER_TRADING
        )

        print(
            "Live Trading      :",
            LIVE_TRADING
        )

        print(
            "Trading Start     :",
            TRADING_START
        )

        print(
            "Last Entry        :",
            LAST_ENTRY_TIME
        )

        print(
            "Square Off        :",
            SQUARE_OFF_TIME
        )

        print(
            "Scan Interval     :",
            SCAN_INTERVAL_SECONDS,
            "seconds"
        )

        print("=" * 100)

        try:

            while self.running:

                self.run_cycle()

                now = self.current_time()

                # Stop the program after square-off
                # when no paper positions remain.

                if (
                    now >= SQUARE_OFF_TIME
                    and
                    not self.paper_engine
                    .open_positions
                ):

                    print()
                    print(
                        "Trading day complete."
                    )

                    break

                time.sleep(
                    SCAN_INTERVAL_SECONDS
                )

        except KeyboardInterrupt:

            print()
            print(
                "Bot stopped manually."
            )

        except Exception as error:

            print()
            print(
                "FATAL BOT ERROR:"
            )

            print(
                type(error).__name__,
                ":",
                error
            )

            raise

        finally:

            print()
            print("=" * 100)
            print("FINAL JOURNAL SUMMARY")
            print("=" * 100)

            print(
                self.journal.summary()
            )

            print("=" * 100)


# ================================================================
# START
# ================================================================

if __name__ == "__main__":

    bot = TradingBot()

    bot.run()