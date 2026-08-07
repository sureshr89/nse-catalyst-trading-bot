"""
PAPER TRADE ENGINE
==================

Simulates approved trades.

Responsibilities
----------------
1. Open an approved paper position
2. Track open positions
3. Check 1-minute candle for SL / Target
4. Mandatory square-off at 15:00
5. Calculate P&L
6. Maintain closed positions

Important
---------
This engine DOES NOT:
- Find setups
- Generate entries
- Calculate market direction
- Place broker orders

If both SL and Target are touched in the same candle,
STOP LOSS is assumed first because OHLC data cannot tell
which level was touched first.
"""

from datetime import datetime

from config.settings import (
    PAPER_TRADING,
    LIVE_TRADING,
    LAST_ENTRY_TIME,
    SQUARE_OFF_TIME,
    MARKET_CLOSE,
)


class PaperTradeEngine:

    def __init__(self):

        self.paper_trading = bool(
            PAPER_TRADING
        )

        self.live_trading = bool(
            LIVE_TRADING
        )

        self.last_entry_time = (
            LAST_ENTRY_TIME
        )

        self.square_off_time = (
            SQUARE_OFF_TIME
        )

        self.market_close = (
            MARKET_CLOSE
        )

        # Current open positions
        #
        # {
        #   "RELIANCE": {...}
        # }

        self.open_positions = {}

        # Completed trades

        self.closed_positions = []

        # Sequential paper trade ID

        self.trade_counter = 0

    # ============================================================
    # TIME HELPERS
    # ============================================================

    def _time_string(
        self,
        value
    ):

        """
        Convert Timestamp / datetime / string
        into HH:MM.
        """

        if value is None:
            return None

        if hasattr(
            value,
            "strftime"
        ):

            return value.strftime(
                "%H:%M"
            )

        text = str(
            value
        ).strip()

        # ISO / pandas style timestamp

        try:

            parsed = datetime.fromisoformat(
                text
            )

            return parsed.strftime(
                "%H:%M"
            )

        except ValueError:

            pass

        # Already HH:MM or HH:MM:SS

        if len(text) >= 5:

            possible = text[-8:]

            if ":" in possible:

                parts = possible.split(":")

                if len(parts) >= 2:

                    hour = parts[0][-2:]

                    minute = parts[1][:2]

                    if (
                        hour.isdigit()
                        and minute.isdigit()
                    ):

                        return (
                            f"{hour}:{minute}"
                        )

        return None

    # ============================================================
    # NUMBER HELPER
    # ============================================================

    def _number(
        self,
        value
    ):

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return None

    # ============================================================
    # OPEN POSITION?
    # ============================================================

    def has_open_position(
        self,
        symbol
    ):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        return (
            symbol
            in self.open_positions
        )

    # ============================================================
    # OPEN TRADE
    # ============================================================

    def open_trade(
        self,
        trade
    ):

        if not self.paper_trading:

            return {
                "opened": False,
                "reason":
                    "Paper trading is disabled"
            }

        if self.live_trading:

            return {
                "opened": False,
                "reason":
                    "Live trading must remain disabled "
                    "while using PaperTradeEngine"
            }

        if not isinstance(
            trade,
            dict
        ):

            return {
                "opened": False,
                "reason":
                    "Trade must be a dictionary"
            }

        # --------------------------------------------------------
        # RISK APPROVAL
        # --------------------------------------------------------

        if not trade.get(
            "approved",
            False
        ):

            return {
                "opened": False,
                "reason":
                    "Trade has not been approved "
                    "by RiskEngine"
            }

        # --------------------------------------------------------
        # VALUES
        # --------------------------------------------------------

        symbol = (
            str(
                trade.get(
                    "symbol",
                    ""
                )
            )
            .strip()
            .upper()
        )

        signal = (
            str(
                trade.get(
                    "signal",
                    ""
                )
            )
            .strip()
            .upper()
        )

        entry = self._number(
            trade.get(
                "entry"
            )
        )

        stop_loss = self._number(
            trade.get(
                "stop_loss"
            )
        )

        target = self._number(
            trade.get(
                "target"
            )
        )

        quantity = self._number(
            trade.get(
                "quantity"
            )
        )

        entry_time = trade.get(
            "entry_time"
        )

        # Test trades may not contain entry_time.
        # Use current time only for paper-engine testing.

        if entry_time is None:

            entry_time = datetime.now()

        entry_hhmm = self._time_string(
            entry_time
        )

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        if not symbol:

            return {
                "opened": False,
                "reason":
                    "Missing symbol"
            }

        if signal not in [
            "BUY",
            "SELL"
        ]:

            return {
                "opened": False,
                "reason":
                    "Invalid signal"
            }

        if (
            entry is None
            or stop_loss is None
            or target is None
            or quantity is None
        ):

            return {
                "opened": False,
                "reason":
                    "Invalid trade values"
            }

        if quantity <= 0:

            return {
                "opened": False,
                "reason":
                    "Quantity must be positive"
            }

        # --------------------------------------------------------
        # ENTRY TIME
        # --------------------------------------------------------

        if entry_hhmm is None:

            return {
                "opened": False,
                "reason":
                    "Unable to determine entry time"
            }

        if (
            entry_hhmm
            >
            self.last_entry_time
        ):

            return {
                "opened": False,
                "reason":
                    f"Entry time {entry_hhmm} is after "
                    f"last entry time "
                    f"{self.last_entry_time}"
            }

        # --------------------------------------------------------
        # DUPLICATE OPEN POSITION
        # --------------------------------------------------------

        if self.has_open_position(
            symbol
        ):

            return {
                "opened": False,
                "reason":
                    f"{symbol} already has "
                    f"an open position"
            }

        # --------------------------------------------------------
        # CREATE TRADE
        # --------------------------------------------------------

        self.trade_counter += 1

        trade_id = (
            f"PAPER-{self.trade_counter:04d}"
        )

        position = {

            "trade_id":
                trade_id,

            "symbol":
                symbol,

            "signal":
                signal,

            "entry_time":
                entry_time,

            "entry":
                round(
                    entry,
                    4
                ),

            "stop_loss":
                round(
                    stop_loss,
                    4
                ),

            "target":
                round(
                    target,
                    4
                ),

            "quantity":
                int(
                    quantity
                ),

            "status":
                "OPEN",

            "exit_time":
                None,

            "exit_price":
                None,

            "exit_reason":
                None,

            "pnl":
                None,
        }

        # Keep useful scanner/risk information

        optional_fields = [

            "industry",

            "market_direction",

            "industry_direction",

            "stock_direction",

            "risk_per_share",

            "actual_risk",

            "position_value",

            "breakout_level",
        ]

        for field in optional_fields:

            if field in trade:

                position[field] = (
                    trade[field]
                )

        self.open_positions[
            symbol
        ] = position

        return {

            "opened":
                True,

            "trade_id":
                trade_id,

            "position":
                position.copy()
        }

    # ============================================================
    # CALCULATE PNL
    # ============================================================

    def calculate_pnl(
        self,
        signal,
        entry,
        exit_price,
        quantity
    ):

        if signal == "BUY":

            pnl = (
                exit_price
                -
                entry
            ) * quantity

        elif signal == "SELL":

            pnl = (
                entry
                -
                exit_price
            ) * quantity

        else:

            pnl = 0.0

        return round(
            pnl,
            2
        )

    # ============================================================
    # CLOSE POSITION
    # ============================================================

    def close_position(
        self,
        symbol,
        exit_price,
        exit_time,
        reason
    ):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not self.has_open_position(
            symbol
        ):

            return None

        position = self.open_positions[
            symbol
        ]

        exit_price = float(
            exit_price
        )

        pnl = self.calculate_pnl(

            position["signal"],

            position["entry"],

            exit_price,

            position["quantity"]
        )

        position["status"] = (
            "CLOSED"
        )

        position["exit_time"] = (
            exit_time
        )

        position["exit_price"] = round(
            exit_price,
            4
        )

        position["exit_reason"] = (
            reason
        )

        position["pnl"] = (
            pnl
        )

        closed = position.copy()

        self.closed_positions.append(
            closed
        )

        del self.open_positions[
            symbol
        ]

        return closed

    # ============================================================
    # CHECK ONE CANDLE
    # ============================================================

    def process_candle(
        self,
        symbol,
        candle
    ):

        """
        candle example:

        {
            "Datetime": timestamp,
            "Open": 105,
            "High": 108,
            "Low": 104,
            "Close": 107
        }
        """

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not self.has_open_position(
            symbol
        ):

            return None

        if not isinstance(
            candle,
            dict
        ):

            try:

                candle = (
                    candle.to_dict()
                )

            except Exception:

                return None

        position = self.open_positions[
            symbol
        ]

        candle_time = (
            candle.get(
                "Datetime"
            )
        )

        if candle_time is None:

            candle_time = (
                candle.get(
                    "datetime"
                )
            )

        high = self._number(
            candle.get(
                "High",
                candle.get(
                    "high"
                )
            )
        )

        low = self._number(
            candle.get(
                "Low",
                candle.get(
                    "low"
                )
            )
        )

        close = self._number(
            candle.get(
                "Close",
                candle.get(
                    "close"
                )
            )
        )

        if (
            high is None
            or low is None
            or close is None
        ):

            return None

        candle_hhmm = self._time_string(
            candle_time
        )

        signal = position[
            "signal"
        ]

        stop_loss = position[
            "stop_loss"
        ]

        target = position[
            "target"
        ]

        # --------------------------------------------------------
        # BUY POSITION
        # --------------------------------------------------------

        if signal == "BUY":

            sl_hit = (
                low <= stop_loss
            )

            target_hit = (
                high >= target
            )

            # If both touched in same candle:
            # conservative assumption = SL first.

            if (
                sl_hit
                and target_hit
            ):

                return self.close_position(
                    symbol,
                    stop_loss,
                    candle_time,
                    "STOP_LOSS"
                )

            if sl_hit:

                return self.close_position(
                    symbol,
                    stop_loss,
                    candle_time,
                    "STOP_LOSS"
                )

            if target_hit:

                return self.close_position(
                    symbol,
                    target,
                    candle_time,
                    "TARGET"
                )

        # --------------------------------------------------------
        # SELL POSITION
        # --------------------------------------------------------

        elif signal == "SELL":

            sl_hit = (
                high >= stop_loss
            )

            target_hit = (
                low <= target
            )

            if (
                sl_hit
                and target_hit
            ):

                return self.close_position(
                    symbol,
                    stop_loss,
                    candle_time,
                    "STOP_LOSS"
                )

            if sl_hit:

                return self.close_position(
                    symbol,
                    stop_loss,
                    candle_time,
                    "STOP_LOSS"
                )

            if target_hit:

                return self.close_position(
                    symbol,
                    target,
                    candle_time,
                    "TARGET"
                )

        # --------------------------------------------------------
        # MANDATORY 15:00 SQUARE-OFF
        #
        # Only after checking SL/Target for that candle.
        # --------------------------------------------------------

        if (
            candle_hhmm is not None
            and
            candle_hhmm
            >=
            self.square_off_time
        ):

            return self.close_position(
                symbol,
                close,
                candle_time,
                "SQUARE_OFF"
            )

        return None

    # ============================================================
    # FORCE SQUARE-OFF ALL
    # ============================================================

    def square_off_all(
        self,
        prices,
        exit_time
    ):

        """
        prices example:

        {
            "RELIANCE": 1325.50,
            "INFY": 1500.00
        }
        """

        closed = []

        symbols = list(
            self.open_positions.keys()
        )

        for symbol in symbols:

            if symbol not in prices:
                continue

            exit_price = self._number(
                prices[symbol]
            )

            if exit_price is None:
                continue

            result = self.close_position(
                symbol,
                exit_price,
                exit_time,
                "SQUARE_OFF"
            )

            if result is not None:

                closed.append(
                    result
                )

        return closed

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self):

        total_pnl = sum(

            trade.get(
                "pnl",
                0
            )

            for trade
            in self.closed_positions
        )

        winning = sum(

            1

            for trade
            in self.closed_positions

            if trade.get(
                "pnl",
                0
            ) > 0
        )

        losing = sum(

            1

            for trade
            in self.closed_positions

            if trade.get(
                "pnl",
                0
            ) < 0
        )

        return {

            "open_positions":
                len(
                    self.open_positions
                ),

            "closed_positions":
                len(
                    self.closed_positions
                ),

            "winning_trades":
                winning,

            "losing_trades":
                losing,

            "total_pnl":
                round(
                    total_pnl,
                    2
                )
        }


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)

    print(
        "PAPER TRADE ENGINE"
    )

    print("=" * 90)

    engine = PaperTradeEngine()

    print(
        "Paper Trading       :",
        engine.paper_trading
    )

    print(
        "Live Trading        :",
        engine.live_trading
    )

    print(
        "Last Entry          :",
        engine.last_entry_time
    )

    print(
        "Square Off          :",
        engine.square_off_time
    )

    # ------------------------------------------------------------
    # TEST 1 - BUY TARGET
    # ------------------------------------------------------------

    buy_trade = {

        "approved":
            True,

        "symbol":
            "RELIANCE",

        "signal":
            "BUY",

        "entry_time":
            datetime(
                2026,
                8,
                6,
                10,
                0
            ),

        "entry":
            105.40,

        "stop_loss":
            102.80,

        "target":
            108.00,

        "quantity":
            480,

        "actual_risk":
            1248.00
    }

    print()

    print(
        "TEST 1 - OPEN BUY"
    )

    print("-" * 90)

    print(
        engine.open_trade(
            buy_trade
        )
    )

    buy_candle = {

        "Datetime":
            datetime(
                2026,
                8,
                6,
                10,
                5
            ),

        "Open":
            105.50,

        "High":
            108.20,

        "Low":
            105.20,

        "Close":
            108.10
    }

    print()

    print(
        "PROCESS BUY TARGET CANDLE"
    )

    print("-" * 90)

    print(
        engine.process_candle(
            "RELIANCE",
            buy_candle
        )
    )

    # ------------------------------------------------------------
    # TEST 2 - SELL STOP LOSS
    # ------------------------------------------------------------

    sell_trade = {

        "approved":
            True,

        "symbol":
            "TCS",

        "signal":
            "SELL",

        "entry_time":
            datetime(
                2026,
                8,
                6,
                11,
                0
            ),

        "entry":
            99.60,

        "stop_loss":
            102.20,

        "target":
            97.00,

        "quantity":
            480,

        "actual_risk":
            1248.00
    }

    print()

    print(
        "TEST 2 - OPEN SELL"
    )

    print("-" * 90)

    print(
        engine.open_trade(
            sell_trade
        )
    )

    sell_candle = {

        "Datetime":
            datetime(
                2026,
                8,
                6,
                11,
                5
            ),

        "Open":
            100.00,

        "High":
            102.30,

        "Low":
            99.80,

        "Close":
            102.00
    }

    print()

    print(
        "PROCESS SELL SL CANDLE"
    )

    print("-" * 90)

    print(
        engine.process_candle(
            "TCS",
            sell_candle
        )
    )

    # ------------------------------------------------------------
    # TEST 3 - 15:00 SQUARE OFF
    # ------------------------------------------------------------

    square_trade = {

        "approved":
            True,

        "symbol":
            "INFY",

        "signal":
            "BUY",

        "entry_time":
            datetime(
                2026,
                8,
                6,
                12,
                0
            ),

        "entry":
            100.00,

        "stop_loss":
            98.00,

        "target":
            102.00,

        "quantity":
            500,

        "actual_risk":
            1000.00
    }

    print()

    print(
        "TEST 3 - OPEN FOR SQUARE OFF"
    )

    print("-" * 90)

    print(
        engine.open_trade(
            square_trade
        )
    )

    square_candle = {

        "Datetime":
            datetime(
                2026,
                8,
                6,
                15,
                0
            ),

        "Open":
            100.50,

        "High":
            101.00,

        "Low":
            100.20,

        "Close":
            100.70
    }

    print()

    print(
        "PROCESS 15:00 CANDLE"
    )

    print("-" * 90)

    print(
        engine.process_candle(
            "INFY",
            square_candle
        )
    )

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------

    print()

    print(
        "SUMMARY"
    )

    print("-" * 90)

    print(
        engine.summary()
    )

    print()

    print("=" * 90)

    print(
        "PAPER TRADE ENGINE TEST COMPLETE"
    )

    print("=" * 90)