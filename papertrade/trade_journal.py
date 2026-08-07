"""
TRADE JOURNAL
=============

Stores trading-bot activity permanently in CSV files.

Files
-----
outputs/trades.csv
outputs/signals.csv

Responsibilities
----------------
1. Create output directory automatically
2. Save completed paper trades
3. Save scanner signals
4. Prevent duplicate trade IDs
5. Read trade history
6. Calculate basic performance summary

The journal does NOT:
- Generate signals
- Approve risk
- Place trades
- Monitor prices
"""

import os
import csv
from datetime import datetime

import pandas as pd

from config.settings import (
    TRADE_LOG_FILE,
    SIGNAL_LOG_FILE,
)


class TradeJournal:

    # ============================================================
    # TRADE CSV COLUMNS
    # ============================================================

    TRADE_COLUMNS = [

        "trade_id",
        "symbol",
        "industry",
        "signal",

        "entry_time",
        "entry",

        "stop_loss",
        "target",
        "quantity",

        "exit_time",
        "exit_price",
        "exit_reason",

        "pnl",

        "risk_per_share",
        "actual_risk",
        "position_value",

        "breakout_level",

        "market_direction",
        "industry_direction",
        "stock_direction",

        "status",
    ]

    # ============================================================
    # SIGNAL CSV COLUMNS
    # ============================================================

    SIGNAL_COLUMNS = [

        "timestamp",
        "symbol",
        "industry",

        "signal",

        "market_direction",
        "industry_direction",
        "stock_direction",

        "breakout_level",
        "entry",
        "stop_loss",
        "target",
        "quantity",

        "approved",
        "reason",
    ]

    # ============================================================
    # INITIALIZE
    # ============================================================

    def __init__(
        self,
        trade_file=TRADE_LOG_FILE,
        signal_file=SIGNAL_LOG_FILE
    ):

        self.trade_file = trade_file

        self.signal_file = signal_file

        self._prepare_files()

    # ============================================================
    # PREPARE DIRECTORY / FILES
    # ============================================================

    def _prepare_files(self):

        trade_directory = os.path.dirname(
            self.trade_file
        )

        signal_directory = os.path.dirname(
            self.signal_file
        )

        if trade_directory:

            os.makedirs(
                trade_directory,
                exist_ok=True
            )

        if signal_directory:

            os.makedirs(
                signal_directory,
                exist_ok=True
            )

        self._create_csv_if_missing(
            self.trade_file,
            self.TRADE_COLUMNS
        )

        self._create_csv_if_missing(
            self.signal_file,
            self.SIGNAL_COLUMNS
        )

    # ============================================================
    # CREATE CSV
    # ============================================================

    def _create_csv_if_missing(
        self,
        file_path,
        columns
    ):

        if os.path.exists(
            file_path
        ):

            return

        with open(
            file_path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=columns
            )

            writer.writeheader()

    # ============================================================
    # NORMALIZE VALUE
    # ============================================================

    def _value(
        self,
        value
    ):

        if value is None:

            return ""

        # pandas Timestamp / datetime

        if hasattr(
            value,
            "isoformat"
        ):

            try:

                return value.isoformat()

            except Exception:

                pass

        return value

    # ============================================================
    # TRADE ALREADY SAVED?
    # ============================================================

    def trade_exists(
        self,
        trade_id
    ):

        if not trade_id:

            return False

        try:

            df = pd.read_csv(
                self.trade_file
            )

        except (
            FileNotFoundError,
            pd.errors.EmptyDataError
        ):

            return False

        if df.empty:

            return False

        if "trade_id" not in df.columns:

            return False

        trade_ids = (
            df["trade_id"]
            .astype(str)
            .str.strip()
        )

        return (
            str(trade_id).strip()
            in trade_ids.values
        )

    # ============================================================
    # LOG CLOSED TRADE
    # ============================================================

    def log_trade(
        self,
        trade
    ):

        if not isinstance(
            trade,
            dict
        ):

            return {

                "saved": False,

                "reason":
                    "Trade must be a dictionary"
            }

        trade_id = (
            str(
                trade.get(
                    "trade_id",
                    ""
                )
            )
            .strip()
        )

        if not trade_id:

            return {

                "saved": False,

                "reason":
                    "Missing trade_id"
            }

        # Only completed trades belong
        # in trades.csv.

        status = (
            str(
                trade.get(
                    "status",
                    ""
                )
            )
            .strip()
            .upper()
        )

        if status != "CLOSED":

            return {

                "saved": False,

                "reason":
                    "Only CLOSED trades can be saved"
            }

        if self.trade_exists(
            trade_id
        ):

            return {

                "saved": False,

                "reason":
                    f"{trade_id} already exists"
            }

        row = {}

        for column in self.TRADE_COLUMNS:

            row[column] = self._value(
                trade.get(
                    column,
                    ""
                )
            )

        with open(
            self.trade_file,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=self.TRADE_COLUMNS
            )

            writer.writerow(
                row
            )

        return {

            "saved": True,

            "trade_id":
                trade_id,

            "file":
                self.trade_file
        }

    # ============================================================
    # LOG SIGNAL
    # ============================================================

    def log_signal(
        self,
        signal
    ):

        if not isinstance(
            signal,
            dict
        ):

            return {

                "saved": False,

                "reason":
                    "Signal must be a dictionary"
            }

        row = {}

        for column in self.SIGNAL_COLUMNS:

            row[column] = self._value(
                signal.get(
                    column,
                    ""
                )
            )

        if not row[
            "timestamp"
        ]:

            row[
                "timestamp"
            ] = datetime.now().isoformat()

        with open(
            self.signal_file,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=self.SIGNAL_COLUMNS
            )

            writer.writerow(
                row
            )

        return {

            "saved": True,

            "file":
                self.signal_file
        }

    # ============================================================
    # GET TRADE HISTORY
    # ============================================================

    def get_trades(
        self
    ):

        try:

            df = pd.read_csv(
                self.trade_file
            )

        except (
            FileNotFoundError,
            pd.errors.EmptyDataError
        ):

            return pd.DataFrame(
                columns=self.TRADE_COLUMNS
            )

        return df

    # ============================================================
    # GET SIGNAL HISTORY
    # ============================================================

    def get_signals(
        self
    ):

        try:

            df = pd.read_csv(
                self.signal_file
            )

        except (
            FileNotFoundError,
            pd.errors.EmptyDataError
        ):

            return pd.DataFrame(
                columns=self.SIGNAL_COLUMNS
            )

        return df

    # ============================================================
    # PERFORMANCE SUMMARY
    # ============================================================

    def summary(
        self
    ):

        df = self.get_trades()

        if df.empty:

            return {

                "total_trades": 0,

                "winning_trades": 0,

                "losing_trades": 0,

                "breakeven_trades": 0,

                "win_rate": 0.0,

                "total_pnl": 0.0,

                "average_pnl": 0.0,
            }

        pnl = pd.to_numeric(
            df["pnl"],
            errors="coerce"
        ).fillna(0.0)

        total_trades = len(
            pnl
        )

        winning = int(
            (pnl > 0).sum()
        )

        losing = int(
            (pnl < 0).sum()
        )

        breakeven = int(
            (pnl == 0).sum()
        )

        if total_trades > 0:

            win_rate = (
                winning
                /
                total_trades
                *
                100
            )

        else:

            win_rate = 0.0

        return {

            "total_trades":
                total_trades,

            "winning_trades":
                winning,

            "losing_trades":
                losing,

            "breakeven_trades":
                breakeven,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "total_pnl":
                round(
                    float(
                        pnl.sum()
                    ),
                    2
                ),

            "average_pnl":
                round(
                    float(
                        pnl.mean()
                    ),
                    2
                ),
        }


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 90)

    print(
        "TRADE JOURNAL"
    )

    print("=" * 90)

    # ------------------------------------------------------------
    # Use separate test files.
    #
    # This prevents the test from polluting
    # the real trades.csv and signals.csv.
    # ------------------------------------------------------------

    test_trade_file = (
        "outputs/test_trades.csv"
    )

    test_signal_file = (
        "outputs/test_signals.csv"
    )

    # Clean previous test data

    for test_file in [
        test_trade_file,
        test_signal_file
    ]:

        if os.path.exists(
            test_file
        ):

            os.remove(
                test_file
            )

    journal = TradeJournal(
        trade_file=test_trade_file,
        signal_file=test_signal_file
    )

    print(
        "Trade File  :",
        journal.trade_file
    )

    print(
        "Signal File :",
        journal.signal_file
    )

    # ------------------------------------------------------------
    # TEST SIGNAL
    # ------------------------------------------------------------

    test_signal = {

        "timestamp":
            datetime(
                2026,
                8,
                6,
                9,
                56
            ),

        "symbol":
            "RELIANCE",

        "industry":
            "Oil Gas & Consumable Fuels",

        "signal":
            "BUY",

        "market_direction":
            "BULLISH",

        "industry_direction":
            "BULLISH",

        "stock_direction":
            "BULLISH",

        "breakout_level":
            105.00,

        "entry":
            105.40,

        "stop_loss":
            102.80,

        "target":
            108.00,

        "quantity":
            480,

        "approved":
            True,

        "reason":
            ""
    }

    print()

    print(
        "TEST 1 - SAVE SIGNAL"
    )

    print("-" * 90)

    print(
        journal.log_signal(
            test_signal
        )
    )

    # ------------------------------------------------------------
    # TEST CLOSED TRADE
    # ------------------------------------------------------------

    test_trade = {

        "trade_id":
            "PAPER-TEST-0001",

        "symbol":
            "RELIANCE",

        "industry":
            "Oil Gas & Consumable Fuels",

        "signal":
            "BUY",

        "entry_time":
            datetime(
                2026,
                8,
                6,
                9,
                56
            ),

        "entry":
            105.40,

        "stop_loss":
            102.80,

        "target":
            108.00,

        "quantity":
            480,

        "exit_time":
            datetime(
                2026,
                8,
                6,
                10,
                5
            ),

        "exit_price":
            108.00,

        "exit_reason":
            "TARGET",

        "pnl":
            1248.00,

        "risk_per_share":
            2.60,

        "actual_risk":
            1248.00,

        "position_value":
            50592.00,

        "breakout_level":
            105.00,

        "market_direction":
            "BULLISH",

        "industry_direction":
            "BULLISH",

        "stock_direction":
            "BULLISH",

        "status":
            "CLOSED"
    }

    print()

    print(
        "TEST 2 - SAVE CLOSED TRADE"
    )

    print("-" * 90)

    print(
        journal.log_trade(
            test_trade
        )
    )

    # ------------------------------------------------------------
    # DUPLICATE TEST
    # ------------------------------------------------------------

    print()

    print(
        "TEST 3 - DUPLICATE TRADE"
    )

    print("-" * 90)

    print(
        journal.log_trade(
            test_trade
        )
    )

    # ------------------------------------------------------------
    # DISPLAY SAVED TRADES
    # ------------------------------------------------------------

    print()

    print(
        "SAVED TRADES"
    )

    print("-" * 90)

    trades = (
        journal.get_trades()
    )

    print(
        trades.to_string(
            index=False
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
        journal.summary()
    )

    print()

    print("=" * 90)

    print(
        "TRADE JOURNAL TEST PASSED"
    )

    print("=" * 90)