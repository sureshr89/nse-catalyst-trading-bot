"""
SETUP ENGINE
============

5-minute pullback setup.

BUY
---
1. Find the highest high of the day so far.
2. Price must pull back from that high.
3. At least MIN_PULLBACK_CANDLES completed 5-minute candles
   must form the pullback.
4. Pullback candles must not make a new high above the
   frozen/reference high.
5. The lowest low of the pullback becomes the pullback low.
6. The setup is valid only after the pullback shows a bounce.
7. The reference high and pullback low are then frozen.
8. EntryEngine waits for a completed 1-minute candle to
   CLOSE above the frozen high.

SELL
----
Exact opposite:
1. Find the lowest low of the day so far.
2. Price pulls up from that low.
3. At least MIN_PULLBACK_CANDLES completed 5-minute candles.
4. Pullback candles must not make a new low below the
   frozen/reference low.
5. Highest high of the pullback becomes the pullback high.
6. Setup is valid only after the pullback shows a downward bounce.
7. Freeze low + pullback high.
8. EntryEngine waits for a completed 1-minute candle to
   CLOSE below the frozen low.
"""

from datetime import time

import pandas as pd

from config.settings import (
    MIN_PULLBACK_CANDLES,
    TRADING_START,
    LAST_ENTRY_TIME,
)


class SetupEngine:

    def __init__(self):

        self.min_pullback_candles = int(
            MIN_PULLBACK_CANDLES
        )

        self.trading_start = self._parse_time(
            TRADING_START
        )

        self.last_entry_time = self._parse_time(
            LAST_ENTRY_TIME
        )

    # ============================================================
    # TIME PARSER
    # ============================================================

    def _parse_time(self, value):

        hour, minute = map(
            int,
            str(value).split(":")
        )

        return time(
            hour,
            minute
        )

    # ============================================================
    # PREPARE DATA
    # ============================================================

    def _prepare_data(self, df):

        if df is None or df.empty:
            return pd.DataFrame()

        data = df.copy()

        required = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close",
        ]

        for column in required:

            if column not in data.columns:
                return pd.DataFrame()

        data["Datetime"] = pd.to_datetime(
            data["Datetime"],
            errors="coerce"
        )

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
        ]:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
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
    # VALID SETUP TIME
    # ============================================================

    def _valid_setup_time(self, timestamp):

        candle_time = timestamp.time()

        return (
            self.trading_start
            <= candle_time
            <= self.last_entry_time
        )

    # ============================================================
    # FIND BUY SETUP
    # ============================================================

    def find_buy_setup(self, df):

        data = self._prepare_data(df)

        if data.empty:
            return None

        minimum_required = (
            self.min_pullback_candles + 1
        )

        if len(data) < minimum_required:
            return None

        # --------------------------------------------------------
        # Search backwards for the most recent valid day high.
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

            reference_candle = data.iloc[
                reference_index
            ]

            frozen_high = float(
                reference_candle["High"]
            )

            reference_time = reference_candle[
                "Datetime"
            ]

            # ----------------------------------------------------
            # Reference high must be the highest high
            # seen up to this point.
            # ----------------------------------------------------

            previous_data = data.iloc[
                :reference_index + 1
            ]

            previous_high = float(
                previous_data["High"].max()
            )

            if frozen_high < previous_high:
                continue

            # ----------------------------------------------------
            # Pullback candles after reference high.
            # ----------------------------------------------------

            pullback = data.iloc[
                reference_index + 1:
            ].copy()

            if len(pullback) < (
                self.min_pullback_candles
            ):
                continue

            # ----------------------------------------------------
            # Pullback must not break the frozen high.
            # ----------------------------------------------------

            if (
                pullback["High"]
                > frozen_high
            ).any():

                continue

            # ----------------------------------------------------
            # Pullback must actually move below the high.
            # ----------------------------------------------------

            pullback_low = float(
                pullback["Low"].min()
            )

            if pullback_low >= frozen_high:
                continue

            # ----------------------------------------------------
            # We need a bounce after the lowest point.
            #
            # Find the candle where the lowest low occurred.
            # ----------------------------------------------------

            lowest_position = (
                pullback["Low"]
                .idxmin()
            )

            lowest_loc = pullback.index.get_loc(
                lowest_position
            )

            # No candle after the lowest point means
            # no confirmed bounce yet.
            if lowest_loc >= len(pullback) - 1:
                continue

            bounce_data = pullback.iloc[
                lowest_loc + 1:
            ]

            # ----------------------------------------------------
            # Bounce confirmation:
            #
            # A later completed 5-minute candle must close
            # above the close of the candle that created the
            # pullback low.
            # ----------------------------------------------------

            low_candle_close = float(
                pullback.loc[
                    lowest_position,
                    "Close"
                ]
            )

            bounce_confirmed = (
                bounce_data["Close"]
                > low_candle_close
            ).any()

            if not bounce_confirmed:
                continue

            # ----------------------------------------------------
            # Setup must have enough candles BEFORE/AROUND
            # the pullback low.
            # ----------------------------------------------------

            if len(pullback) < (
                self.min_pullback_candles
            ):
                continue

            # ----------------------------------------------------
            # Only a completed 5-minute candle can create
            # the setup.
            # ----------------------------------------------------

            latest_candle = pullback.iloc[-1]

            if not self._valid_setup_time(
                latest_candle["Datetime"]
            ):
                continue

            latest_close = float(
                latest_candle["Close"]
            )

            # ----------------------------------------------------
            # Return frozen BUY setup.
            # ----------------------------------------------------

            return {
                "setup": "BUY",
                "valid": True,

                "reference_index":
                    int(reference_index),

                "reference_time":
                    reference_time,

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

                "bounce_time":
                    bounce_data.iloc[0][
                        "Datetime"
                    ],

                "latest_5m_close":
                    round(
                        latest_close,
                        2
                    ),
            }

        return None

    # ============================================================
    # FIND SELL SETUP
    # ============================================================

    def find_sell_setup(self, df):

        data = self._prepare_data(df)

        if data.empty:
            return None

        minimum_required = (
            self.min_pullback_candles + 1
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

            reference_candle = data.iloc[
                reference_index
            ]

            frozen_low = float(
                reference_candle["Low"]
            )

            reference_time = reference_candle[
                "Datetime"
            ]

            # ----------------------------------------------------
            # Reference low must be the lowest low
            # seen up to this point.
            # ----------------------------------------------------

            previous_data = data.iloc[
                :reference_index + 1
            ]

            previous_low = float(
                previous_data["Low"].min()
            )

            if frozen_low > previous_low:
                continue

            # ----------------------------------------------------
            # Pullback candles after reference low.
            # ----------------------------------------------------

            pullback = data.iloc[
                reference_index + 1:
            ].copy()

            if len(pullback) < (
                self.min_pullback_candles
            ):
                continue

            # ----------------------------------------------------
            # Pullback must not break the frozen low.
            # ----------------------------------------------------

            if (
                pullback["Low"]
                < frozen_low
            ).any():

                continue

            # ----------------------------------------------------
            # Pullback must actually move above the low.
            # ----------------------------------------------------

            pullback_high = float(
                pullback["High"].max()
            )

            if pullback_high <= frozen_low:
                continue

            # ----------------------------------------------------
            # Find highest point of pullback.
            # ----------------------------------------------------

            highest_position = (
                pullback["High"]
                .idxmax()
            )

            highest_loc = pullback.index.get_loc(
                highest_position
            )

            # No candle after highest point means
            # no confirmed downward bounce yet.
            if highest_loc >= len(pullback) - 1:
                continue

            bounce_data = pullback.iloc[
                highest_loc + 1:
            ]

            # ----------------------------------------------------
            # Downward bounce confirmation:
            #
            # A later completed 5-minute candle must close
            # below the close of the candle that created the
            # pullback high.
            # ----------------------------------------------------

            high_candle_close = float(
                pullback.loc[
                    highest_position,
                    "Close"
                ]
            )

            bounce_confirmed = (
                bounce_data["Close"]
                < high_candle_close
            ).any()

            if not bounce_confirmed:
                continue

            if len(pullback) < (
                self.min_pullback_candles
            ):
                continue

            latest_candle = pullback.iloc[-1]

            if not self._valid_setup_time(
                latest_candle["Datetime"]
            ):
                continue

            latest_close = float(
                latest_candle["Close"]
            )

            # ----------------------------------------------------
            # Return frozen SELL setup.
            # ----------------------------------------------------

            return {
                "setup": "SELL",
                "valid": True,

                "reference_index":
                    int(reference_index),

                "reference_time":
                    reference_time,

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

                "bounce_time":
                    bounce_data.iloc[0][
                        "Datetime"
                    ],

                "latest_5m_close":
                    round(
                        latest_close,
                        2
                    ),
            }

        return None

    # ============================================================
    # GENERAL ANALYZE
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
    print(
        "Setup Engine imported successfully."
    )

    print("=" * 90)