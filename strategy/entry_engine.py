from datetime import time
import math

import pandas as pd

from config.settings import (
    TRADING_START,
    LAST_ENTRY_TIME,
    RISK_REWARD_RATIO,
    MAX_RISK_PER_TRADE,
    TOTAL_CAPITAL
)


class EntryEngine:

    def __init__(self):

        self.trading_start = self._parse_time(
            TRADING_START
        )

        self.last_entry_time = self._parse_time(
            LAST_ENTRY_TIME
        )

        self.risk_reward = float(
            RISK_REWARD_RATIO
        )

        self.max_risk = float(
            MAX_RISK_PER_TRADE
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
    # PREPARE 1-MINUTE DATA
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
            "Close"
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
            "Close"
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
    # CHECK ENTRY TIME
    # ============================================================

    def _valid_entry_time(self, timestamp):

        candle_time = timestamp.time()

        return (
            self.trading_start
            <= candle_time
            <= self.last_entry_time
        )

    # ============================================================
    # POSITION SIZE
    # ============================================================

    def calculate_quantity(
            self,
            entry,
            stop_loss,
            available_capital=TOTAL_CAPITAL
    ):
        risk_per_share = abs(entry - stop_loss)

        if risk_per_share <= 0:
            return 0

        risk_quantity = math.floor(
            self.max_risk / risk_per_share
        )

        if risk_quantity <= 0:
            return 0

        required_capital = (
            risk_quantity * entry
        )

        # Take trade ONLY if we have enough capital
        # to build the FULL ₹1250 risk position.

        if required_capital > available_capital:
            return 0

        return risk_quantity



    # ============================================================
    # BUILD BUY TRADE
    # ============================================================

    def _build_buy_trade(
        self,
        candle,
        setup,
        available_capital=TOTAL_CAPITAL
    ):

        entry = float(
            candle["Close"]
        )

        stop_loss = float(
            setup["pullback_low"]
        )

        risk_per_share = (
            entry - stop_loss
        )

        if risk_per_share <= 0:
            return None

        target = (
            entry
            + (
                risk_per_share
                * self.risk_reward
            )
        )

        quantity = self.calculate_quantity(
            entry,
            stop_loss,
            available_capital
        )

        if quantity <= 0:
            return None

        actual_risk = (
            risk_per_share
            * quantity
        )

        return {

            "signal": "BUY",

            "entry_time":
                candle["Datetime"],

            "entry":
                round(
                    entry,
                    2
                ),

            "breakout_level":
                round(
                    float(
                        setup["frozen_high"]
                    ),
                    2
                ),

            "stop_loss":
                round(
                    stop_loss,
                    2
                ),

            "risk_per_share":
                round(
                    risk_per_share,
                    2
                ),

            "target":
                round(
                    target,
                    2
                ),

            "risk_reward":
                self.risk_reward,

            "quantity":
                quantity,

            "maximum_risk":
                round(
                    self.max_risk,
                    2
                ),

            "actual_risk":
                round(
                    actual_risk,
                    2
                ),

            "breakout_candle_open":
                round(
                    float(
                        candle["Open"]
                    ),
                    2
                ),

            "breakout_candle_high":
                round(
                    float(
                        candle["High"]
                    ),
                    2
                ),

            "breakout_candle_low":
                round(
                    float(
                        candle["Low"]
                    ),
                    2
                ),

            "breakout_candle_close":
                round(
                    float(
                        candle["Close"]
                    ),
                    2
                )
        }

    # ============================================================
    # BUILD SELL TRADE
    # ============================================================

    def _build_sell_trade(
        self,
        candle,
        setup,
        available_capital=TOTAL_CAPITAL
    ):

        entry = float(
            candle["Close"]
        )

        stop_loss = float(
            setup["pullback_high"]
        )

        risk_per_share = (
            stop_loss - entry
        )

        if risk_per_share <= 0:
            return None

        target = (
            entry
            - (
                risk_per_share
                * self.risk_reward
            )
        )

        quantity = self.calculate_quantity(
            entry,
            stop_loss,
            available_capital
        )

        if quantity <= 0:
            return None

        actual_risk = (
            risk_per_share
            * quantity
        )

        return {

            "signal": "SELL",

            "entry_time":
                candle["Datetime"],

            "entry":
                round(
                    entry,
                    2
                ),

            "breakout_level":
                round(
                    float(
                        setup["frozen_low"]
                    ),
                    2
                ),

            "stop_loss":
                round(
                    stop_loss,
                    2
                ),

            "risk_per_share":
                round(
                    risk_per_share,
                    2
                ),

            "target":
                round(
                    target,
                    2
                ),

            "risk_reward":
                self.risk_reward,

            "quantity":
                quantity,

            "maximum_risk":
                round(
                    self.max_risk,
                    2
                ),

            "actual_risk":
                round(
                    actual_risk,
                    2
                ),

            "breakout_candle_open":
                round(
                    float(
                        candle["Open"]
                    ),
                    2
                ),

            "breakout_candle_high":
                round(
                    float(
                        candle["High"]
                    ),
                    2
                ),

            "breakout_candle_low":
                round(
                    float(
                        candle["Low"]
                    ),
                    2
                ),

            "breakout_candle_close":
                round(
                    float(
                        candle["Close"]
                    ),
                    2
                )
        }

    # ============================================================
    # FIND BUY ENTRY
    # ============================================================

    def find_buy_entry(
        self,
        df_1m,
        setup
    ):

        if not setup:
            return None

        if setup.get("setup") != "BUY":
            return None

        if not setup.get(
            "valid",
            False
        ):
            return None

        data = self._prepare_data(
            df_1m
        )

        if data.empty:
            return None

        frozen_high = float(
            setup["frozen_high"]
        )

        pullback_end = pd.Timestamp(
            setup["pullback_end"]
        )

        # Only candles AFTER the completed
        # 5-minute pullback can trigger entry.

        candidates = data[
            data["Datetime"]
            > pullback_end
        ].copy()

        if candidates.empty:
            return None

        for _, candle in candidates.iterrows():

            timestamp = candle[
                "Datetime"
            ]

            if not self._valid_entry_time(
                timestamp
            ):
                continue

            # High touching/crossing is NOT enough.
            # 1-minute CLOSE must be above frozen high.

            if float(
                candle["Close"]
            ) > frozen_high:

                return self._build_buy_trade(
                    candle,
                    setup,
                    TOTAL_CAPITAL
                )

        return None

    # ============================================================
    # FIND SELL ENTRY
    # ============================================================

    def find_sell_entry(
        self,
        df_1m,
        setup
    ):

        if not setup:
            return None

        if setup.get("setup") != "SELL":
            return None

        if not setup.get(
            "valid",
            False
        ):
            return None

        data = self._prepare_data(
            df_1m
        )

        if data.empty:
            return None

        frozen_low = float(
            setup["frozen_low"]
        )

        pullback_end = pd.Timestamp(
            setup["pullback_end"]
        )

        candidates = data[
            data["Datetime"]
            > pullback_end
        ].copy()

        if candidates.empty:
            return None

        for _, candle in candidates.iterrows():

            timestamp = candle[
                "Datetime"
            ]

            if not self._valid_entry_time(
                timestamp
            ):
                continue

            # Low touching/crossing is NOT enough.
            # 1-minute CLOSE must be below frozen low.

            if float(
                candle["Close"]
            ) < frozen_low:

                return self._build_sell_trade(
                    candle,
                    setup,
                    TOTAL_CAPITAL
                )

        return None

    # ============================================================
    # GENERAL ENTRY METHOD
    # ============================================================

    def find_entry(
        self,
        df_1m,
        setup
    ):

        if not setup:
            return None

        setup_type = str(
            setup.get(
                "setup",
                ""
            )
        ).upper()

        if setup_type == "BUY":

            return self.find_buy_entry(
                df_1m,
                setup
            )

        if setup_type == "SELL":

            return self.find_sell_entry(
                df_1m,
                setup
            )

        return None


# ================================================================
# BUY TEST DATA
# ================================================================

def create_buy_test():

    times = pd.date_range(
        "2026-08-06 09:51",
        periods=6,
        freq="1min",
        tz="Asia/Kolkata"
    )

    data = pd.DataFrame({

        "Datetime": times,

        "Open": [
            104.00,
            104.20,
            104.50,
            104.80,
            104.90,
            105.10
        ],

        "High": [
            104.30,
            104.60,
            104.90,
            105.10,
            105.20,
            105.60
        ],

        "Low": [
            103.90,
            104.10,
            104.40,
            104.60,
            104.70,
            105.00
        ],

        "Close": [
            104.20,
            104.50,
            104.80,
            104.90,

            # Candle high crossed 105,
            # but close remains below.
            # NO ENTRY.
            104.95,

            # Completed 1-minute candle
            # closes above 105.
            # VALID ENTRY.
            105.40
        ]
    })

    setup = {

        "setup": "BUY",

        "valid": True,

        "frozen_high": 105.00,

        "pullback_low": 102.80,

        "pullback_end": pd.Timestamp(
            "2026-08-06 09:50",
            tz="Asia/Kolkata"
        )
    }

    return data, setup


# ================================================================
# SELL TEST DATA
# ================================================================

def create_sell_test():

    times = pd.date_range(
        "2026-08-06 09:51",
        periods=6,
        freq="1min",
        tz="Asia/Kolkata"
    )

    data = pd.DataFrame({

        "Datetime": times,

        "Open": [
            101.00,
            100.80,
            100.60,
            100.40,
            100.20,
            99.90
        ],

        "High": [
            101.20,
            101.00,
            100.80,
            100.60,
            100.40,
            100.00
        ],

        "Low": [
            100.80,
            100.60,
            100.40,
            100.20,

            # Candle low crossed 100,
            # but close remains above.
            99.80,

            99.40
        ],

        "Close": [
            100.90,
            100.70,
            100.50,
            100.30,

            # NO ENTRY
            100.05,

            # VALID SELL
            99.60
        ]
    })

    setup = {

        "setup": "SELL",

        "valid": True,

        "frozen_low": 100.00,

        "pullback_high": 102.20,

        "pullback_end": pd.Timestamp(
            "2026-08-06 09:50",
            tz="Asia/Kolkata"
        )
    }

    return data, setup


# ================================================================
# MAIN TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)
    print("1-MINUTE ENTRY ENGINE")
    print("=" * 90)

    engine = EntryEngine()

    print(
        "Trading Start     :",
        TRADING_START
    )

    print(
        "Last Entry        :",
        LAST_ENTRY_TIME
    )

    print(
        "Risk Reward       :",
        f"1:{engine.risk_reward}"
    )

    print(
        "Maximum Risk      :",
        f"Rs {engine.max_risk:.2f}"
    )

    print()

    # ============================================================
    # BUY TEST
    # ============================================================

    buy_data, buy_setup = (
        create_buy_test()
    )

    print("BUY TEST")
    print("-" * 90)

    print(
        buy_data.to_string(
            index=False
        )
    )

    print()

    buy_trade = (
        engine.find_buy_entry(
            buy_data,
            buy_setup
        )
    )

    print("BUY TRADE")
    print("-" * 90)

    print(
        buy_trade
    )

    print()

    # ============================================================
    # SELL TEST
    # ============================================================

    sell_data, sell_setup = (
        create_sell_test()
    )

    print("SELL TEST")
    print("-" * 90)

    print(
        sell_data.to_string(
            index=False
        )
    )

    print()

    sell_trade = (
        engine.find_sell_entry(
            sell_data,
            sell_setup
        )
    )

    print("SELL TRADE")
    print("-" * 90)

    print(
        sell_trade
    )

    print()

    # ============================================================
    # VALIDATION
    # ============================================================

    buy_pass = (
        buy_trade is not None
        and buy_trade["signal"] == "BUY"
        and buy_trade["entry"] == 105.40
        and buy_trade["stop_loss"] == 102.80
        and buy_trade["target"] == 108.00
        and buy_trade["quantity"] == 480
    )

    sell_pass = (
        sell_trade is not None
        and sell_trade["signal"] == "SELL"
        and sell_trade["entry"] == 99.60
        and sell_trade["stop_loss"] == 102.20
        and sell_trade["target"] == 97.00
        and sell_trade["quantity"] == 480
    )

    print("=" * 90)

    if buy_pass and sell_pass:

        print(
            "ENTRY ENGINE TEST PASSED"
        )

    else:

        print(
            "ENTRY ENGINE TEST FAILED"
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