"""
SETUP ENGINE
============

Detects the 5-minute pullback structure for the strategy.

BUY SETUP
---------
1. Stock direction must already be BULLISH.
2. Price makes a reference high.
3. At least 2 completed 5-minute candles occur after that high.
4. Those pullback candles must NOT break the reference high.
5. Reference high becomes the FROZEN HIGH.
6. Lowest low of the pullback candles becomes PULLBACK LOW.
7. Later, a completed 1-minute candle must CLOSE above the
   frozen high to trigger the BUY.

SELL SETUP
----------
1. Stock direction must already be BEARISH.
2. Price makes a reference low.
3. At least 2 completed 5-minute candles occur after that low.
4. Those pullback candles must NOT break the reference low.
5. Reference low becomes the FROZEN LOW.
6. Highest high of the pullback candles becomes PULLBACK HIGH.
7. Later, a completed 1-minute candle must CLOSE below the
   frozen low to trigger the SELL.

IMPORTANT
---------
This engine only identifies the 5-minute setup.

It does NOT execute trades.

The 1-minute breakout confirmation will be handled by the
entry engine.
"""

from datetime import time

import pandas as pd

from config.settings import (
    MIN_PULLBACK_CANDLES,
    TRADING_START,
    LAST_ENTRY_TIME
)


class SetupEngine:

    def __init__(self):

        self.min_pullback_candles = (
            MIN_PULLBACK_CANDLES
        )

        self.trading_start = (
            self._parse_time(
                TRADING_START
            )
        )

        self.last_entry_time = (
            self._parse_time(
                LAST_ENTRY_TIME
            )
        )

    # ============================================================
    # TIME PARSER
    # ============================================================

    def _parse_time(self, value):

        hour, minute = map(
            int,
            value.split(":")
        )

        return time(
            hour,
            minute
        )

    # ============================================================
    # VALIDATE DATA
    # ============================================================

    def _prepare_data(
        self,
        df
    ):

        if df is None or df.empty:

            return pd.DataFrame()

        data = df.copy()

        required = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close"
        ]

        for column in required:

            if column not in data.columns:

                return pd.DataFrame()

        data["Datetime"] = (
            pd.to_datetime(
                data["Datetime"],
                errors="coerce"
            )
        )

        for column in [
            "Open",
            "High",
            "Low",
            "Close"
        ]:

            data[column] = (
                pd.to_numeric(
                    data[column],
                    errors="coerce"
                )
            )

        data = data.dropna(
            subset=required
        )

        data = (
            data
            .sort_values("Datetime")
            .drop_duplicates(
                subset=["Datetime"]
            )
            .reset_index(drop=True)
        )

        return data

    # ============================================================
    # FIND BUY SETUP
    # ============================================================

    def find_buy_setup(
        self,
        df
    ):

        data = self._prepare_data(
            df
        )

        if data.empty:

            return None

        minimum_required = (
            self.min_pullback_candles
            + 1
        )

        if len(data) < minimum_required:

            return None

        # --------------------------------------------------------
        # SEARCH BACKWARDS
        #
        # We want the most recent valid reference high followed
        # by at least MIN_PULLBACK_CANDLES completed candles.
        # --------------------------------------------------------

        latest_reference_index = (
            len(data)
            - self.min_pullback_candles
            - 1
        )

        for reference_index in range(
            latest_reference_index,
            -1,
            -1
        ):

            reference_candle = (
                data.iloc[
                    reference_index
                ]
            )

            frozen_high = float(
                reference_candle[
                    "High"
                ]
            )

            # ----------------------------------------------------
            # Reference high must be the highest high seen
            # up to that candle.
            # ----------------------------------------------------

            previous_data = (
                data.iloc[
                    :reference_index + 1
                ]
            )

            previous_high = float(
                previous_data[
                    "High"
                ].max()
            )

            if frozen_high < previous_high:

                continue

            # ----------------------------------------------------
            # Candles after reference high
            # ----------------------------------------------------

            pullback = (
                data.iloc[
                    reference_index + 1:
                ]
                .copy()
            )

            if (
                len(pullback)
                < self.min_pullback_candles
            ):

                continue

            # ----------------------------------------------------
            # Pullback must remain BELOW / AT frozen high.
            #
            # If any later 5m candle makes a higher high,
            # the old frozen high is no longer valid.
            # ----------------------------------------------------

            if (
                pullback["High"]
                > frozen_high
            ).any():

                continue

            pullback_low = float(
                pullback["Low"]
                .min()
            )

            latest_close = float(
                pullback.iloc[-1][
                    "Close"
                ]
            )

            # Stop must be below potential entry area.
            if pullback_low >= frozen_high:

                continue

            return {

                "setup": "BUY",

                "valid": True,

                "reference_index":
                    int(reference_index),

                "reference_time":
                    reference_candle[
                        "Datetime"
                    ],

                "frozen_high":
                    round(
                        frozen_high,
                        2
                    ),

                "pullback_low":
                    round(
                        pullback_low,
                        2
                    ),

                "pullback_candles":
                    len(pullback),

                "pullback_start":
                    pullback.iloc[0][
                        "Datetime"
                    ],

                "pullback_end":
                    pullback.iloc[-1][
                        "Datetime"
                    ],

                "latest_5m_close":
                    round(
                        latest_close,
                        2
                    )
            }

        return None

    # ============================================================
    # FIND SELL SETUP
    # ============================================================

    def find_sell_setup(
        self,
        df
    ):

        data = self._prepare_data(
            df
        )

        if data.empty:

            return None

        minimum_required = (
            self.min_pullback_candles
            + 1
        )

        if len(data) < minimum_required:

            return None

        latest_reference_index = (
            len(data)
            - self.min_pullback_candles
            - 1
        )

        for reference_index in range(
            latest_reference_index,
            -1,
            -1
        ):

            reference_candle = (
                data.iloc[
                    reference_index
                ]
            )

            frozen_low = float(
                reference_candle[
                    "Low"
                ]
            )

            # ----------------------------------------------------
            # Reference low must be the lowest low seen
            # up to that candle.
            # ----------------------------------------------------

            previous_data = (
                data.iloc[
                    :reference_index + 1
                ]
            )

            previous_low = float(
                previous_data[
                    "Low"
                ].min()
            )

            if frozen_low > previous_low:

                continue

            # ----------------------------------------------------
            # Candles after reference low
            # ----------------------------------------------------

            pullback = (
                data.iloc[
                    reference_index + 1:
                ]
                .copy()
            )

            if (
                len(pullback)
                < self.min_pullback_candles
            ):

                continue

            # ----------------------------------------------------
            # Pullback must remain ABOVE / AT frozen low.
            #
            # If a later 5m candle makes a lower low,
            # the old frozen low is invalid.
            # ----------------------------------------------------

            if (
                pullback["Low"]
                < frozen_low
            ).any():

                continue

            pullback_high = float(
                pullback["High"]
                .max()
            )

            latest_close = float(
                pullback.iloc[-1][
                    "Close"
                ]
            )

            if pullback_high <= frozen_low:

                continue

            return {

                "setup": "SELL",

                "valid": True,

                "reference_index":
                    int(reference_index),

                "reference_time":
                    reference_candle[
                        "Datetime"
                    ],

                "frozen_low":
                    round(
                        frozen_low,
                        2
                    ),

                "pullback_high":
                    round(
                        pullback_high,
                        2
                    ),

                "pullback_candles":
                    len(pullback),

                "pullback_start":
                    pullback.iloc[0][
                        "Datetime"
                    ],

                "pullback_end":
                    pullback.iloc[-1][
                        "Datetime"
                    ],

                "latest_5m_close":
                    round(
                        latest_close,
                        2
                    )
            }

        return None

    # ============================================================
    # ANALYZE BASED ON DIRECTION
    # ============================================================

    def analyze(
        self,
        df,
        direction
    ):

        direction = (
            str(direction)
            .strip()
            .upper()
        )

        if direction == "BULLISH":

            return self.find_buy_setup(
                df
            )

        if direction == "BEARISH":

            return self.find_sell_setup(
                df
            )

        return None


# ================================================================
# TEST DATA
# ================================================================

def create_buy_test_data():

    times = pd.date_range(
        "2026-08-06 09:15",
        periods=8,
        freq="5min",
        tz="Asia/Kolkata"
    )

    return pd.DataFrame({

        "Datetime": times,

        "Open": [
            100.00,
            101.00,
            102.00,
            103.00,
            104.00,
            103.70,
            103.20,
            103.50
        ],

        "High": [
            101.00,
            102.00,
            103.00,
            104.00,
            105.00,
            104.20,
            103.80,
            104.30
        ],

        "Low": [
            99.50,
            100.50,
            101.50,
            102.50,
            103.50,
            103.00,
            102.80,
            103.10
        ],

        "Close": [
            100.80,
            101.80,
            102.80,
            103.80,
            104.70,
            103.30,
            103.40,
            104.00
        ]
    })


def create_sell_test_data():

    times = pd.date_range(
        "2026-08-06 09:15",
        periods=8,
        freq="5min",
        tz="Asia/Kolkata"
    )

    return pd.DataFrame({

        "Datetime": times,

        "Open": [
            105.00,
            104.00,
            103.00,
            102.00,
            101.00,
            101.30,
            101.70,
            101.40
        ],

        "High": [
            105.50,
            104.50,
            103.50,
            102.50,
            101.50,
            102.00,
            102.20,
            101.90
        ],

        "Low": [
            104.00,
            103.00,
            102.00,
            101.00,
            100.00,
            100.80,
            100.50,
            100.70
        ],

        "Close": [
            104.20,
            103.20,
            102.20,
            101.20,
            100.30,
            101.50,
            101.20,
            101.00
        ]
    })


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("5-MINUTE PULLBACK SETUP ENGINE")
    print("=" * 90)

    engine = SetupEngine()

    print(
        "Minimum Pullback Candles :",
        engine.min_pullback_candles
    )

    print()

    # ------------------------------------------------------------
    # BUY TEST
    # ------------------------------------------------------------

    buy_data = (
        create_buy_test_data()
    )

    buy_result = (
        engine.find_buy_setup(
            buy_data
        )
    )

    print("BUY TEST")
    print("-" * 90)

    print(
        buy_data.to_string(
            index=False
        )
    )

    print()

    print(
        "BUY RESULT :",
        buy_result
    )

    print()

    # ------------------------------------------------------------
    # SELL TEST
    # ------------------------------------------------------------

    sell_data = (
        create_sell_test_data()
    )

    sell_result = (
        engine.find_sell_setup(
            sell_data
        )
    )

    print("SELL TEST")
    print("-" * 90)

    print(
        sell_data.to_string(
            index=False
        )
    )

    print()

    print(
        "SELL RESULT:",
        sell_result
    )

    print()

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    buy_pass = (
        buy_result is not None
        and buy_result[
            "frozen_high"
        ] == 105.00
        and buy_result[
            "pullback_low"
        ] == 102.80
    )

    sell_pass = (
        sell_result is not None
        and sell_result[
            "frozen_low"
        ] == 100.00
        and sell_result[
            "pullback_high"
        ] == 102.20
    )

    print("=" * 90)

    if (
        buy_pass
        and sell_pass
    ):

        print(
            "SETUP ENGINE TEST PASSED"
        )

    else:

        print(
            "SETUP ENGINE TEST FAILED"
        )

        print(
            "BUY PASS :",
            buy_pass
        )

        print(
            "SELL PASS:",
            sell_pass
        )

    print("=" * 90)