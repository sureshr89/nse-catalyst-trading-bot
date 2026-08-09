"""
RISK ENGINE
===========

Final safety gate between a scanner signal and a paper trade.

Checks
------
1. Signal must be BUY or SELL
2. Entry must be valid
3. Stop loss must be valid
4. Target must be valid
5. Quantity must be positive integer
6. BUY stop loss must be below entry
7. SELL stop loss must be above entry
8. BUY target must be above entry
9. SELL target must be below entry
10. Risk per share must be positive
11. Actual trade risk must be >= MIN_REQUIRED_RISK
12. Actual trade risk must not exceed MAX_RISK_PER_TRADE
13. Position value must not exceed TOTAL_CAPITAL
14. Same stock cannot exceed MAX_TRADES_PER_STOCK

This engine does NOT place orders.
"""

from config.settings import (
    TOTAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    MIN_REQUIRED_RISK,
    RISK_PERCENT,
    MAX_TRADES_PER_STOCK,
)


class RiskEngine:

    def __init__(self):

        self.total_capital = float(
            TOTAL_CAPITAL
        )

        self.max_risk_per_trade = float(
            MAX_RISK_PER_TRADE
        )

        self.min_required_risk = float(
            MIN_REQUIRED_RISK
        )

        self.risk_percent = float(
            RISK_PERCENT
        )

        self.max_trades_per_stock = int(
            MAX_TRADES_PER_STOCK
        )

        # --------------------------------------------------------
        # Trades accepted during this program session.
        # --------------------------------------------------------

        self.trade_counts = {}

    # ============================================================
    # SAFE NUMBER CONVERSION
    # ============================================================

    def _number(self, value):

        try:

            number = float(value)

            if not number == number:
                return None

            return number

        except (
            TypeError,
            ValueError
        ):

            return None

    # ============================================================
    # TRADE COUNT
    # ============================================================

    def get_trade_count(self, symbol):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        return self.trade_counts.get(
            symbol,
            0
        )

    # ============================================================
    # CAN STOCK TRADE?
    # ============================================================

    def stock_trade_allowed(self, symbol):

        count = self.get_trade_count(
            symbol
        )

        return (
            count <
            self.max_trades_per_stock
        )

    # ============================================================
    # REGISTER APPROVED TRADE
    # ============================================================

    def register_trade(self, symbol):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        current = self.get_trade_count(
            symbol
        )

        self.trade_counts[symbol] = (
            current + 1
        )

        return self.trade_counts[
            symbol
        ]

    # ============================================================
    # RESET SESSION COUNTS
    # ============================================================

    def reset_trade_counts(self):

        self.trade_counts = {}

    # ============================================================
    # CALCULATE RISK
    # ============================================================

    def calculate_risk(
        self,
        signal,
        entry,
        stop_loss,
        quantity
    ):

        signal = (
            str(signal)
            .strip()
            .upper()
        )

        entry = self._number(
            entry
        )

        stop_loss = self._number(
            stop_loss
        )

        quantity = self._number(
            quantity
        )

        if (
            entry is None
            or stop_loss is None
            or quantity is None
        ):

            return None

        if quantity <= 0:

            return None

        if signal == "BUY":

            risk_per_share = (
                entry - stop_loss
            )

        elif signal == "SELL":

            risk_per_share = (
                stop_loss - entry
            )

        else:

            return None

        if risk_per_share <= 0:

            return None

        actual_risk = (
            risk_per_share
            *
            quantity
        )

        position_value = (
            entry
            *
            quantity
        )

        return {

            "risk_per_share":
                round(
                    risk_per_share,
                    4
                ),

            "actual_risk":
                round(
                    actual_risk,
                    2
                ),

            "position_value":
                round(
                    position_value,
                    2
                ),
        }

    # ============================================================
    # VALIDATE TRADE
    # ============================================================

    def validate(
        self,
        trade,
        check_trade_count=True
    ):

        reasons = []

        # --------------------------------------------------------
        # TRADE OBJECT
        # --------------------------------------------------------

        if not isinstance(
            trade,
            dict
        ):

            return {

                "approved": False,

                "reasons": [
                    "Trade must be a dictionary"
                ]
            }

        # --------------------------------------------------------
        # SYMBOL
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

        if not symbol:

            reasons.append(
                "Missing symbol"
            )

        # --------------------------------------------------------
        # SIGNAL
        # --------------------------------------------------------

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

        if signal not in [
            "BUY",
            "SELL"
        ]:

            reasons.append(
                "Signal must be BUY or SELL"
            )

        # --------------------------------------------------------
        # NUMBERS
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # BASIC VALIDATION
        # --------------------------------------------------------

        if (
            entry is None
            or entry <= 0
        ):

            reasons.append(
                "Invalid entry price"
            )

        if (
            stop_loss is None
            or stop_loss <= 0
        ):

            reasons.append(
                "Invalid stop loss"
            )

        if (
            target is None
            or target <= 0
        ):

            reasons.append(
                "Invalid target"
            )

        if (
            quantity is None
            or quantity <= 0
        ):

            reasons.append(
                "Invalid quantity"
            )

        # Quantity must be a whole number.
        if (
            quantity is not None
            and quantity > 0
            and quantity != int(quantity)
        ):

            reasons.append(
                "Quantity must be a whole number"
            )

        # --------------------------------------------------------
        # STOP LOSS / TARGET DIRECTION
        # --------------------------------------------------------

        if (
            signal == "BUY"
            and entry is not None
            and stop_loss is not None
        ):

            if stop_loss >= entry:

                reasons.append(
                    "BUY stop loss must be below entry"
                )

            if (
                target is not None
                and target <= entry
            ):

                reasons.append(
                    "BUY target must be above entry"
                )

        if (
            signal == "SELL"
            and entry is not None
            and stop_loss is not None
        ):

            if stop_loss <= entry:

                reasons.append(
                    "SELL stop loss must be above entry"
                )

            if (
                target is not None
                and target >= entry
            ):

                reasons.append(
                    "SELL target must be below entry"
                )

        # --------------------------------------------------------
        # STOP IF BASIC VALUES ARE INVALID
        # --------------------------------------------------------

        if reasons:

            return {

                "approved": False,

                "symbol": symbol,

                "signal": signal,

                "reasons": reasons
            }

        # --------------------------------------------------------
        # RECALCULATE RISK
        #
        # Never trust risk values supplied by another module.
        # --------------------------------------------------------

        risk = self.calculate_risk(
            signal,
            entry,
            stop_loss,
            quantity
        )

        if risk is None:

            return {

                "approved": False,

                "symbol": symbol,

                "signal": signal,

                "reasons": [
                    "Unable to calculate valid risk"
                ]
            }

        risk_per_share = risk[
            "risk_per_share"
        ]

        actual_risk = risk[
            "actual_risk"
        ]

        position_value = risk[
            "position_value"
        ]

        # --------------------------------------------------------
        # MINIMUM RISK
        # --------------------------------------------------------

        if (
            actual_risk
            <
            self.min_required_risk
        ):

            reasons.append(

                f"Actual risk Rs {actual_risk:.2f} "
                f"is below minimum required "
                f"Rs {self.min_required_risk:.2f}"
            )

        # --------------------------------------------------------
        # MAXIMUM RISK
        # --------------------------------------------------------

        if (
            actual_risk
            >
            self.max_risk_per_trade
        ):

            reasons.append(

                f"Actual risk Rs {actual_risk:.2f} "
                f"exceeds maximum "
                f"Rs {self.max_risk_per_trade:.2f}"
            )

        # --------------------------------------------------------
        # CAPITAL LIMIT
        # --------------------------------------------------------

        if (
            position_value
            >
            self.total_capital
        ):

            reasons.append(

                f"Position value Rs {position_value:.2f} "
                f"exceeds capital "
                f"Rs {self.total_capital:.2f}"
            )

        # --------------------------------------------------------
        # MAX TRADES PER STOCK
        # --------------------------------------------------------

        if (
            check_trade_count
            and
            not self.stock_trade_allowed(
                symbol
            )
        ):

            reasons.append(

                f"{symbol} already reached "
                f"maximum trades per stock "
                f"({self.max_trades_per_stock})"
            )

        # --------------------------------------------------------
        # FINAL RESULT
        # --------------------------------------------------------

        approved = (
            len(reasons) == 0
        )

        return {

            "approved":
                approved,

            "symbol":
                symbol,

            "signal":
                signal,

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
                int(quantity),

            "risk_per_share":
                risk_per_share,

            "actual_risk":
                actual_risk,

            "position_value":
                position_value,

            "min_required_risk":
                self.min_required_risk,

            "max_risk":
                self.max_risk_per_trade,

            "capital":
                self.total_capital,

            "reasons":
                reasons
        }

    # ============================================================
    # APPROVE AND REGISTER
    # ============================================================

    def approve_trade(self, trade):

        result = self.validate(
            trade,
            check_trade_count=True
        )

        if not result[
            "approved"
        ]:

            return result

        # Only register after successful validation.

        self.register_trade(
            result["symbol"]
        )

        result[
            "trade_count"
        ] = self.get_trade_count(
            result["symbol"]
        )

        return result


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("RISK ENGINE")
    print("=" * 90)

    engine = RiskEngine()

    print(
        "Total Capital        :",
        f"Rs {engine.total_capital:.2f}"
    )

    print(
        "Minimum Risk / Trade :",
        f"Rs {engine.min_required_risk:.2f}"
    )

    print(
        "Maximum Risk / Trade :",
        f"Rs {engine.max_risk_per_trade:.2f}"
    )

    print(
        "Risk Percent         :",
        f"{engine.risk_percent}%"
    )

    print(
        "Max Trades / Stock   :",
        engine.max_trades_per_stock
    )

    # ------------------------------------------------------------
    # TEST 1 - VALID BUY
    # ------------------------------------------------------------

    buy_trade = {

        "symbol":
            "RELIANCE",

        "signal":
            "BUY",

        "entry":
            105.40,

        "stop_loss":
            102.80,

        "target":
            108.00,

        "quantity":
            480
    }

    print()
    print(
        "TEST 1 - VALID BUY"
    )
    print("-" * 90)

    result = engine.approve_trade(
        buy_trade
    )

    print(result)

    # ------------------------------------------------------------
    # TEST 2 - DUPLICATE STOCK
    # ------------------------------------------------------------

    print()
    print(
        "TEST 2 - SECOND RELIANCE TRADE"
    )
    print("-" * 90)

    result = engine.approve_trade(
        buy_trade
    )

    print(result)

    # ------------------------------------------------------------
    # TEST 3 - BELOW MINIMUM RISK
    # ------------------------------------------------------------

    low_risk_trade = {

        "symbol":
            "INFY",

        "signal":
            "BUY",

        "entry":
            100.00,

        "stop_loss":
            99.00,

        "target":
            101.00,

        "quantity":
            500
    }

    print()
    print(
        "TEST 3 - BELOW MINIMUM RISK"
    )
    print("-" * 90)

    result = engine.approve_trade(
        low_risk_trade
    )

    print(result)

    # ------------------------------------------------------------
    # TEST 4 - EXCESS RISK
    # ------------------------------------------------------------

    high_risk_trade = {

        "symbol":
            "HDFCBANK",

        "signal":
            "BUY",

        "entry":
            100.00,

        "stop_loss":
            95.00,

        "target":
            105.00,

        "quantity":
            500
    }

    print()
    print(
        "TEST 4 - EXCESS RISK"
    )
    print("-" * 90)

    result = engine.approve_trade(
        high_risk_trade
    )

    print(result)

    # ------------------------------------------------------------
    # TEST 5 - VALID SELL
    # ------------------------------------------------------------

    sell_trade = {

        "symbol":
            "TCS",

        "signal":
            "SELL",

        "entry":
            99.60,

        "stop_loss":
            102.20,

        "target":
            97.00,

        "quantity":
            480
    }

    print()
    print(
        "TEST 5 - VALID SELL"
    )
    print("-" * 90)

    result = engine.approve_trade(
        sell_trade
    )

    print(result)

    print()
    print("=" * 90)
    print(
        "RISK ENGINE TEST COMPLETE"
    )
    print("=" * 90)