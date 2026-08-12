import time
from datetime import datetime, timedelta

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
    COOLDOWN_MINUTES,
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
                "This bot is for paper trading only."
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

        self.processed_signals = set()

        self.daily_pnl = self._restore_daily_pnl()

        self.cooldown_until = None

        self.square_off_done = False

    def _restore_daily_pnl(self):

        try:
            df = self.journal.get_trades()
            if df.empty or "pnl" not in df.columns:
                return 0.0
            today = datetime.now().strftime("%Y-%m-%d")
            exit_dates = df["exit_time"].astype(str).str[:10]
            pnl = __import__("pandas").to_numeric(df["pnl"], errors="coerce").fillna(0.0)
            return round(float(pnl[exit_dates == today].sum()), 2)
        except Exception as error:
            print(f"Daily P&L restore skipped: {type(error).__name__}: {error}")
            return 0.0

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
            signal.get(
                "symbol",
                ""
            )
        ).strip().upper()

        side = str(
            signal.get(
                "signal",
                ""
            )
        ).strip().upper()

        entry_time = str(
            signal.get(
                "entry_time",
                ""
            )
        )

        breakout_level = str(
            signal.get(
                "breakout_level",
                ""
            )
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

    def log_signal(
        self,
        signal,
        risk_result
    ):

        journal_signal = dict(
            signal
        )

        journal_signal[
            "timestamp"
        ] = signal.get(
            "entry_time",
            datetime.now()
        )

        journal_signal[
            "approved"
        ] = risk_result.get(
            "approved",
            False
        )

        reasons = risk_result.get(
            "reasons",
            []
        )

        if isinstance(
            reasons,
            list
        ):

            reason_text = "; ".join(
                str(reason)
                for reason in reasons
            )

        else:

            reason_text = str(
                reasons
            )

        journal_signal[
            "reason"
        ] = reason_text

        self.journal.log_signal(
            journal_signal
        )

    # ============================================================
    # DAILY LIMIT
    # ============================================================

    def daily_limit_reached(self):

        if (
            self.daily_pnl
            <= -DAILY_MAX_LOSS
        ):

            print(
                "Daily max loss reached."
            )

            return True

        if (
            self.daily_pnl
            >= DAILY_PROFIT_TARGET
        ):

            print(
                "Daily profit target reached."
            )

            return True

        return False

    # ============================================================
    # COOLDOWN
    # ============================================================

    def cooldown_active(self):

        if self.cooldown_until is None:
            return False

        now = datetime.now()

        if now >= self.cooldown_until:

            self.cooldown_until = None

            return False

        return True

    # ============================================================
    # PROCESS ONE SCANNER SIGNAL
    # ============================================================

    def process_signal(self, signal):

        if not isinstance(
            signal,
            dict
        ):

            return

        symbol = str(
            signal.get(
                "symbol",
                ""
            )
        ).strip().upper()

        if not symbol:
            return

        key = self.signal_key(
            signal
        )

        # --------------------------------------------------------
        # DO NOT PROCESS SAME SIGNAL TWICE
        # --------------------------------------------------------

        if key in self.processed_signals:

            return

        # --------------------------------------------------------
        # DAILY LIMIT
        # --------------------------------------------------------

        if self.daily_limit_reached():

            return

        # --------------------------------------------------------
        # COOLDOWN
        # --------------------------------------------------------

        if self.cooldown_active():

            print(
                "Cooldown active until:",
                self.cooldown_until
            )

            return

        # --------------------------------------------------------
        # MAX OPEN POSITIONS
        # --------------------------------------------------------

        open_count = len(
            self.paper_engine.open_positions
        )

        if (
            open_count
            >= MAX_OPEN_POSITIONS
        ):

            print(
                "Maximum open positions reached:",
                MAX_OPEN_POSITIONS
            )

            return

        # --------------------------------------------------------
        # EXISTING POSITION
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
        # MARK SIGNAL AS PROCESSED
        #
        # Only after basic eligibility checks.
        # --------------------------------------------------------

        self.processed_signals.add(
            key
        )

        print()
        print("-" * 100)

        print(
            "PROCESSING SIGNAL :",
            symbol,
            signal.get(
                "signal"
            )
        )

        print("-" * 100)

        # --------------------------------------------------------
        # RISK APPROVAL
        # --------------------------------------------------------

        risk_result = (
            self.risk_engine.approve_trade(
                signal
            )
        )

        # --------------------------------------------------------
        # SAVE APPROVED / REJECTED SIGNAL
        # --------------------------------------------------------

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
                "Risk Rejection    :",
                risk_result.get(
                    "reasons",
                    []
                )
            )

            return

        # --------------------------------------------------------
        # COMBINE SIGNAL + RISK
        # --------------------------------------------------------

        approved_trade = dict(
            signal
        )

        approved_trade.update(
            risk_result
        )

        approved_trade[
            "approved"
        ] = True

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
            position[
                "trade_id"
            ]
        )

        print(
            "Symbol            :",
            position[
                "symbol"
            ]
        )

        print(
            "Signal            :",
            position[
                "signal"
            ]
        )

        print(
            "Entry             :",
            position[
                "entry"
            ]
        )

        print(
            "Stop Loss         :",
            position[
                "stop_loss"
            ]
        )

        print(
            "Target            :",
            position[
                "target"
            ]
        )

        print(
            "Quantity          :",
            position[
                "quantity"
            ]
        )

        print(
            "Actual Risk       :",
            position.get(
                "actual_risk"
            )
        )

        # Persist the open entry immediately so a reboot cannot lose it.
        position["status"] = "OPEN"
        entry_save = self.journal.log_trade(position)
        print(
            "Entry Journal Saved:",
            entry_save.get("saved", False)
        )

    # ============================================================
    # SCAN FOR NEW ENTRIES
    # ============================================================

    def scan_for_entries(self):

        now = self.current_time()

        # --------------------------------------------------------
        # BEFORE 09:45
        # --------------------------------------------------------

        if now < TRADING_START:

            print(
                "Waiting for trading start:",
                TRADING_START
            )

            return

        # --------------------------------------------------------
        # AFTER 13:30
        # --------------------------------------------------------

        if now > LAST_ENTRY_TIME:

            print(
                "New-entry window closed."
            )

            return

        # --------------------------------------------------------
        # DAILY LIMIT
        # --------------------------------------------------------

        if self.daily_limit_reached():

            return

        # --------------------------------------------------------
        # COOLDOWN
        # --------------------------------------------------------

        if self.cooldown_active():

            print(
                "Cooldown active until:",
                self.cooldown_until
            )

            return

        # --------------------------------------------------------
        # MAX POSITIONS
        # --------------------------------------------------------

        if (
            len(
                self.paper_engine.open_positions
            )
            >= MAX_OPEN_POSITIONS
        ):

            print(
                "Maximum open positions reached."
            )

            return

        # --------------------------------------------------------
        # SCANNER
        # --------------------------------------------------------

        signals = self.scanner.scan()

        if signals is None:

            signals = []

        if not isinstance(
            signals,
            list
        ):

            print(
                "WARNING: Scanner returned "
                "unexpected data."
            )

            return

        for signal in signals:

            if (
                len(
                    self.paper_engine
                    .open_positions
                )
                >= MAX_OPEN_POSITIONS
            ):

                print(
                    "Maximum open positions reached."
                )

                break

            self.process_signal(
                signal
            )

    # ============================================================
    # GET LATEST 1-MINUTE CANDLE
    # ============================================================

    def latest_1m_candle(
        self,
        symbol
    ):

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

        if (
            df is None
            or df.empty
        ):

            return None

        try:

            today_df = (
                self.price_data.today_only(
                    df
                )
            )

            if (
                today_df is not None
                and not today_df.empty
            ):

                df = today_df

        except Exception:
            pass

        if df.empty:

            return None

        # --------------------------------------------------------
        # IMPORTANT
        #
        # Never use the currently forming candle.
        #
        # The latest row may still be forming.
        # Therefore use the previous completed row.
        # --------------------------------------------------------

        if len(df) < 2:

            return None

        row = df.iloc[-2]

        try:

            candle = row.to_dict()

        except Exception:

            return None

        if (
            "Datetime" not in candle
            or candle.get(
                "Datetime"
            ) is None
        ):

            candle[
                "Datetime"
            ] = row.name

        return candle

    # ============================================================
    # MONITOR ONE POSITION
    # ============================================================

    def monitor_position(
        self,
        symbol
    ):

        candle = (
            self.latest_1m_candle(
                symbol
            )
        )

        if candle is None:

            print(
                symbol,
                ": no completed 1-minute candle."
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

        print(
            "PAPER TRADE CLOSED"
        )

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

        pnl = float(
            closed_trade.get(
                "pnl",
                0
            )
        )

        self.daily_pnl += pnl

        # --------------------------------------------------------
        # COOLDOWN ONLY AFTER STOP LOSS
        # --------------------------------------------------------

        exit_reason = str(
            closed_trade.get(
                "exit_reason",
                ""
            )
        ).upper()

        if exit_reason == "STOP_LOSS":

            self.cooldown_until = (
                datetime.now()
                + timedelta(
                    minutes=COOLDOWN_MINUTES
                )
            )

            print(
                "Cooldown Until   :",
                self.cooldown_until
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
    # FORCE SQUARE OFF
    # ============================================================

    def force_square_off(self):

        symbols = list(
            self.paper_engine
            .open_positions
            .keys()
        )

        if not symbols:
            return

        print()
        print("=" * 100)
        print("MANDATORY 15:00 SQUARE-OFF")
        print("=" * 100)

        for symbol in symbols:

            position = self.paper_engine.open_positions.get(symbol)
            if position is None:
                continue

            # Mandatory square-off must NOT depend on a completed candle.
            # First try the latest completed candle; if unavailable, use the
            # latest available 1-minute close. This guarantees the position
            # is closed at/after 15:00 instead of being left open.
            candle = self.latest_1m_candle(symbol)
            exit_price = None
            exit_time = datetime.now()

            if candle is not None:
                exit_price = candle.get("Close", candle.get("close"))
                exit_time = candle.get("Datetime", candle.get("datetime")) or exit_time

            if exit_price is None:
                try:
                    df = self.price_data.get_1m(symbol)
                    if df is not None and not df.empty:
                        row = df.iloc[-1]
                        exit_price = row.get("Close", row.get("close"))
                        exit_time = row.get("Datetime", row.get("datetime")) or row.name or exit_time
                except Exception as error:
                    print(symbol, "latest price fallback error:", error)

            if exit_price is None:
                print(symbol, ": NO EXIT PRICE AVAILABLE; position remains protected for retry.")
                continue

            try:
                exit_price = float(exit_price)
            except (TypeError, ValueError):
                print(symbol, ": invalid square-off price:", exit_price)
                continue

            closed_trade = self.paper_engine.close_position(
                symbol,
                exit_price,
                exit_time,
                "SQUARE_OFF"
            )

            if closed_trade is None:
                continue

            pnl = float(closed_trade.get("pnl", 0) or 0)
            self.daily_pnl += pnl

            save_result = self.journal.log_trade(closed_trade)

            print(
                symbol,
                "SQUARE_OFF",
                "Exit:", closed_trade.get("exit_price"),
                "P&L:", pnl,
                "Journal Saved:", save_result.get("saved", False)
            )

        print("Remaining Open Positions:", len(self.paper_engine.open_positions))
        print("=" * 100)

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
        print(
            "BOT STATUS"
        )
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

        print(
            "Available Capital :",
            session[
                "available_capital"
            ]
        )

        print(
            "Used Capital      :",
            session[
                "used_capital"
            ]
        )

        print(
            "Daily P&L          :",
            round(
                self.daily_pnl,
                2
            )
        )

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

        print(
            "Cooldown Until    :",
            self.cooldown_until
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

        # --------------------------------------------------------
        # 15:00 SQUARE-OFF
        # --------------------------------------------------------

        if now >= SQUARE_OFF_TIME:

            if not self.square_off_done:

                self.force_square_off()

                self.square_off_done = True

            self.display_status()

            return

        # --------------------------------------------------------
        # MANAGE EXISTING POSITIONS
        # --------------------------------------------------------

        self.monitor_open_positions()

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
            "Max Positions     :",
            MAX_OPEN_POSITIONS
        )

        print(
            "Cooldown           :",
            COOLDOWN_MINUTES,
            "minutes"
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

                # ------------------------------------------------
                # Stop after square-off once all positions closed.
                # ------------------------------------------------

                if (
                    now >= SQUARE_OFF_TIME
                    and not
                    self.paper_engine
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

            print(
                "FINAL JOURNAL SUMMARY"
            )

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