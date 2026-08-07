"""
NIFTY LARGEMIDCAP 250 SCANNER ENGINE
====================================

Flow
----
250 Stocks
    ↓
NIFTY Direction
    ↓
Industry Breadth
    ↓
Stock Direction
    ↓
Alignment
    ↓
5-Minute Pullback Setup
    ↓
1-Minute Breakout Confirmation
    ↓
Trade Candidate

BUY
---
NIFTY    = BULLISH
Industry = BULLISH
Stock    = BULLISH

Then:
Valid 5-minute BUY pullback
1-minute CLOSE above frozen high

SELL
----
NIFTY    = BEARISH
Industry = BEARISH
Stock    = BEARISH

Then:
Valid 5-minute SELL pullback
1-minute CLOSE below frozen low
"""

from data.stock_universe import StockUniverse

from market.price_data import PriceData
from market.market_direction import MarketDirection
from market.industry_direction import IndustryDirection

from strategy.setup_engine import SetupEngine
from strategy.entry_engine import EntryEngine


class ScannerEngine:

    def __init__(self):

        self.universe = StockUniverse()

        self.price_data = PriceData()

        self.market_engine = MarketDirection()

        self.industry_engine = IndustryDirection()

        self.setup_engine = SetupEngine()

        self.entry_engine = EntryEngine()

    # ============================================================
    # LOAD SYMBOLS
    # ============================================================

    def load_symbols(self):

        symbols = self.universe.get_symbols(
            refresh=False
        )

        return symbols

    # ============================================================
    # MARKET DIRECTION
    # ============================================================

    def get_market_direction(self):

        result = self.market_engine.analyze()

        if not result:
            return "NEUTRAL"

        direction = str(
            result.get(
                "direction",
                "NEUTRAL"
            )
        ).strip().upper()

        return direction

    # ============================================================
    # ALIGNMENT
    # ============================================================

    def check_alignment(
        self,
        market_direction,
        industry_direction,
        stock_direction
    ):

        market_direction = str(
            market_direction
        ).strip().upper()

        industry_direction = str(
            industry_direction
        ).strip().upper()

        stock_direction = str(
            stock_direction
        ).strip().upper()

        # BUY ALIGNMENT

        if (
            market_direction == "BULLISH"
            and
            industry_direction == "BULLISH"
            and
            stock_direction == "BULLISH"
        ):

            return "BULLISH"

        # SELL ALIGNMENT

        if (
            market_direction == "BEARISH"
            and
            industry_direction == "BEARISH"
            and
            stock_direction == "BEARISH"
        ):

            return "BEARISH"

        return None

    # ============================================================
    # SCAN ONE STOCK
    # ============================================================

    def scan_stock(
        self,
        symbol,
        market_direction
    ):

        # --------------------------------------------------------
        # STOCK DIRECTION
        # --------------------------------------------------------

        stock_direction = (
            self.industry_engine
            .get_stock_direction(
                symbol
            )
        )

        if stock_direction == "UNKNOWN":
            return None

        # --------------------------------------------------------
        # FIND STOCK INDUSTRY
        #
        # IndustryDirection already contains stock_results
        # generated during analyze().
        # --------------------------------------------------------

        stock_results = (
            self.industry_engine
            .stock_results
        )

        if (
            stock_results is None
            or stock_results.empty
        ):
            return None

        match = stock_results[
            stock_results["Symbol"]
            == symbol
        ]

        if match.empty:
            return None

        industry = str(
            match.iloc[0]["Industry"]
        ).strip()

        # --------------------------------------------------------
        # INDUSTRY DIRECTION
        # --------------------------------------------------------

        industry_direction = (
            self.industry_engine
            .get_industry_direction(
                industry
            )
        )

        if industry_direction == "UNKNOWN":
            return None

        # --------------------------------------------------------
        # ALIGNMENT
        # --------------------------------------------------------

        setup_direction = (
            self.check_alignment(
                market_direction,
                industry_direction,
                stock_direction
            )
        )

        if setup_direction is None:
            return None

        # --------------------------------------------------------
        # GET 5-MINUTE STOCK DATA
        # --------------------------------------------------------

        df_5m = self.price_data.get_5m(
            symbol
        )

        if (
            df_5m is None
            or df_5m.empty
        ):
            return None

        df_5m = self.price_data.today_only(
            df_5m
        )

        if (
            df_5m is None
            or df_5m.empty
        ):
            return None

        # --------------------------------------------------------
        # FIND 5-MINUTE PULLBACK
        #
        # SetupEngine expects:
        #
        # BULLISH
        # or
        # BEARISH
        # --------------------------------------------------------

        setup = self.setup_engine.analyze(
            df_5m,
            setup_direction
        )

        if setup is None:
            return None

        if not setup.get(
            "valid",
            False
        ):
            return None

        # --------------------------------------------------------
        # GET 1-MINUTE DATA
        #
        # We download 1-minute data only if a valid
        # 5-minute setup exists.
        # --------------------------------------------------------

        df_1m = self.price_data.get_1m(
            symbol
        )

        if (
            df_1m is None
            or df_1m.empty
        ):
            return None

        df_1m = self.price_data.today_only(
            df_1m
        )

        if (
            df_1m is None
            or df_1m.empty
        ):
            return None

        # --------------------------------------------------------
        # FINAL ENTRY CONFIRMATION
        # --------------------------------------------------------

        trade = self.entry_engine.find_entry(
            df_1m,
            setup
        )

        if trade is None:
            return None

        # --------------------------------------------------------
        # ADD SCANNER INFORMATION
        # --------------------------------------------------------

        trade["symbol"] = symbol

        trade["industry"] = industry

        trade["market_direction"] = (
            market_direction
        )

        trade["industry_direction"] = (
            industry_direction
        )

        trade["stock_direction"] = (
            stock_direction
        )

        return trade

    # ============================================================
    # FULL SCAN
    # ============================================================

    def scan(self):

        print("=" * 110)

        print(
            "NIFTY LARGEMIDCAP 250 "
            "PULLBACK BREAKOUT SCANNER"
        )

        print("=" * 110)

        # --------------------------------------------------------
        # LOAD 250 SYMBOLS
        # --------------------------------------------------------

        symbols = self.load_symbols()

        print(
            "Stocks Loaded       :",
            len(symbols)
        )

        if not symbols:

            print(
                "ERROR: Stock universe is empty."
            )

            return []

        # --------------------------------------------------------
        # NIFTY DIRECTION
        # --------------------------------------------------------

        print()

        print(
            "Checking NIFTY direction..."
        )

        market_direction = (
            self.get_market_direction()
        )

        print(
            "NIFTY Direction     :",
            market_direction
        )

        # --------------------------------------------------------
        # DO NOTHING IF NIFTY NEUTRAL
        # --------------------------------------------------------

        if market_direction not in [
            "BULLISH",
            "BEARISH"
        ]:

            print()

            print(
                "NIFTY is NEUTRAL."
            )

            print(
                "No new trades allowed."
            )

            print("=" * 110)

            return []

        # --------------------------------------------------------
        # INDUSTRY / STOCK ANALYSIS
        # --------------------------------------------------------

        print()

        print(
            "Analyzing industry and "
            "stock directions..."
        )

        stock_results, industry_results = (
            self.industry_engine.analyze()
        )

        if (
            stock_results is None
            or stock_results.empty
        ):

            print(
                "ERROR: Stock direction "
                "analysis unavailable."
            )

            return []

        if (
            industry_results is None
            or industry_results.empty
        ):

            print(
                "ERROR: Industry direction "
                "analysis unavailable."
            )

            return []

        print(
            "Stocks Analyzed     :",
            len(stock_results)
        )

        print(
            "Industries Analyzed :",
            len(industry_results)
        )

        # --------------------------------------------------------
        # FIND ALIGNED STOCKS FIRST
        #
        # Important:
        # Do NOT download 5m/1m data for all 250 again.
        # First filter using the breadth results.
        # --------------------------------------------------------

        aligned = []

        for symbol in symbols:

            stock_direction = (
                self.industry_engine
                .get_stock_direction(
                    symbol
                )
            )

            match = stock_results[
                stock_results["Symbol"]
                == symbol
            ]

            if match.empty:
                continue

            industry = str(
                match.iloc[0]["Industry"]
            ).strip()

            industry_direction = (
                self.industry_engine
                .get_industry_direction(
                    industry
                )
            )

            setup_direction = (
                self.check_alignment(
                    market_direction,
                    industry_direction,
                    stock_direction
                )
            )

            if setup_direction is None:
                continue

            aligned.append(
                {
                    "symbol": symbol,
                    "industry": industry,
                    "direction":
                        setup_direction,
                    "stock_direction":
                        stock_direction,
                    "industry_direction":
                        industry_direction
                }
            )

        print()

        print(
            "Aligned Stocks      :",
            len(aligned)
        )

        # --------------------------------------------------------
        # SHOW ALIGNED STOCKS
        # --------------------------------------------------------

        if aligned:

            print()

            print(
                "ALIGNED STOCKS"
            )

            print("-" * 110)

            for number, item in enumerate(
                aligned,
                start=1
            ):

                print(
                    f"{number:3}. "
                    f"{item['symbol']:15} "
                    f"{item['direction']:8} "
                    f"{item['industry']}"
                )

        else:

            print()

            print(
                "No stocks currently aligned."
            )

            print("=" * 110)

            return []

        # --------------------------------------------------------
        # SCAN ONLY ALIGNED STOCKS
        # --------------------------------------------------------

        print()

        print(
            "Checking 5-minute "
            "pullback setups..."
        )

        print("-" * 110)

        signals = []

        setup_count = 0

        for number, item in enumerate(
            aligned,
            start=1
        ):

            symbol = item["symbol"]

            print(
                f"Scanning "
                f"{number}/{len(aligned)} "
                f": {symbol}"
            )

            try:

                # ----------------------------------------------
                # GET 5-MINUTE DATA
                # ----------------------------------------------

                df_5m = (
                    self.price_data.get_5m(
                        symbol
                    )
                )

                if (
                    df_5m is None
                    or df_5m.empty
                ):
                    continue

                df_5m = (
                    self.price_data.today_only(
                        df_5m
                    )
                )

                if (
                    df_5m is None
                    or df_5m.empty
                ):
                    continue

                # ----------------------------------------------
                # SETUP
                # ----------------------------------------------

                setup = (
                    self.setup_engine.analyze(
                        df_5m,
                        item["direction"]
                    )
                )

                if setup is None:
                    continue

                if not setup.get(
                    "valid",
                    False
                ):
                    continue

                setup_count += 1

                print(
                    f"   VALID 5m "
                    f"{setup['setup']} SETUP"
                )

                # ----------------------------------------------
                # ONLY NOW GET 1-MINUTE DATA
                # ----------------------------------------------

                df_1m = (
                    self.price_data.get_1m(
                        symbol
                    )
                )

                if (
                    df_1m is None
                    or df_1m.empty
                ):
                    continue

                df_1m = (
                    self.price_data.today_only(
                        df_1m
                    )
                )

                if (
                    df_1m is None
                    or df_1m.empty
                ):
                    continue

                # ----------------------------------------------
                # ENTRY
                # ----------------------------------------------

                trade = (
                    self.entry_engine.find_entry(
                        df_1m,
                        setup
                    )
                )

                if trade is None:

                    print(
                        "   Waiting for "
                        "1m confirmation"
                    )

                    continue

                # ----------------------------------------------
                # COMPLETE SIGNAL
                # ----------------------------------------------

                trade["symbol"] = symbol

                trade["industry"] = (
                    item["industry"]
                )

                trade[
                    "market_direction"
                ] = market_direction

                trade[
                    "industry_direction"
                ] = item[
                    "industry_direction"
                ]

                trade[
                    "stock_direction"
                ] = item[
                    "stock_direction"
                ]

                signals.append(
                    trade
                )

                print(
                    f"   >>> "
                    f"{trade['signal']} SIGNAL <<<"
                )

            except Exception as error:

                print(
                    f"   ERROR: {error}"
                )

        # --------------------------------------------------------
        # FINAL SUMMARY
        # --------------------------------------------------------

        print()

        print("=" * 110)

        print(
            "SCAN SUMMARY"
        )

        print("=" * 110)

        print(
            "NIFTY Direction     :",
            market_direction
        )

        print(
            "Universe            :",
            len(symbols)
        )

        print(
            "Aligned Stocks      :",
            len(aligned)
        )

        print(
            "Valid 5m Setups     :",
            setup_count
        )

        print(
            "Final Signals       :",
            len(signals)
        )

        # --------------------------------------------------------
        # DISPLAY SIGNALS
        # --------------------------------------------------------

        if signals:

            print()

            print(
                "TRADE CANDIDATES"
            )

            print("-" * 110)

            for number, trade in enumerate(
                signals,
                start=1
            ):

                print()

                print(
                    f"{number}. "
                    f"{trade['symbol']} "
                    f"{trade['signal']}"
                )

                print(
                    "Industry       :",
                    trade["industry"]
                )

                print(
                    "Entry Time     :",
                    trade["entry_time"]
                )

                print(
                    "Entry          :",
                    trade["entry"]
                )

                print(
                    "Breakout Level :",
                    trade["breakout_level"]
                )

                print(
                    "Stop Loss      :",
                    trade["stop_loss"]
                )

                print(
                    "Target         :",
                    trade["target"]
                )

                print(
                    "Quantity       :",
                    trade["quantity"]
                )

                print(
                    "Risk / Share   :",
                    trade["risk_per_share"]
                )

                print(
                    "Actual Risk    :",
                    trade["actual_risk"]
                )

        else:

            print()

            print(
                "NO FINAL TRADE SIGNALS"
            )

        print()

        print("=" * 110)

        return signals


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":

    scanner = ScannerEngine()

    scanner.scan()