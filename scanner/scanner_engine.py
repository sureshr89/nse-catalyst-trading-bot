"""NIFTY 100 Gap-Failure + Open-Reclaim scanner."""
import pandas as pd
from data.stock_universe import StockUniverse
from data.reference_store import ReferenceStore
from data.sector_store import SectorStore
from market.price_data import PriceData
from strategy.gap_reclaim_engine import GapReclaimEngine
from config.settings import TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO


class ScannerEngine:
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = GapReclaimEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame()
        self.sectors = pd.DataFrame()
        self._prepared_date = None

    def prepare_reference_data(self, force=False):
        """Prepare PDC/previous-day direction and sector mapping before entries."""
        today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
        if not force and self._prepared_date == today and not self.references.empty:
            return self.references
        self.universe = self.universe_engine.get_dataframe(refresh=True)
        self.references = ReferenceStore(self.universe).prepare()
        self.sectors = SectorStore(self.universe).prepare()
        self._prepared_date = today
        print("PRE-MARKET REFERENCES READY:", len(self.references), "stocks")
        return self.references

    @staticmethod
    def _direction(df):
        if df is None or df.empty:
            return "UNKNOWN"
        day_open = float(df.iloc[0]["Open"])
        close = float(df.iloc[-1]["Close"])
        return "BULLISH" if close > day_open else "BEARISH" if close < day_open else "NEUTRAL"

    def _nifty100_direction(self):
        return self._direction(self.price_data.get_index_1m("^CNX100"))

    def _sector_directions(self, market_data):
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        rows = []
        for symbol, df in market_data.items():
            if df is None or df.empty:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            if not sector or sector == "UNKNOWN":
                continue
            direction = self._direction(df)
            if direction in {"BULLISH", "BEARISH"}:
                rows.append((sector, direction))
        if not rows:
            return {}
        frame = pd.DataFrame(rows, columns=["Sector", "Direction"])
        result = {}
        for sector, group in frame.groupby("Sector"):
            bullish = int((group["Direction"] == "BULLISH").sum())
            bearish = int((group["Direction"] == "BEARISH").sum())
            result[sector] = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "NEUTRAL"
        return result

    def scan(self):
        print("=" * 110)
        print("NIFTY 100 GAP-FAILURE + OPEN-RECLAIM PRICE-ACTION SCANNER")
        print("=" * 110)
        self.prepare_reference_data()
        if self.references.empty:
            print("No pre-market reference data. No trades.")
            return []

        symbols = self.references["Symbol"].astype(str).str.upper().tolist()
        print("Stocks Loaded:", len(symbols))
        nifty_direction = self._nifty100_direction()
        print("NIFTY 100 Direction:", nifty_direction)
        if nifty_direction not in {"BULLISH", "BEARISH"}:
            print("NIFTY 100 is neutral/unavailable. No new trades.")
            return []

        market_data = self.price_data.get_multi_1m(symbols)
        sector_directions = self._sector_directions(market_data)
        reference_by_symbol = self.references.set_index("Symbol").to_dict("index")
        sector_map = dict(zip(self.sectors["Symbol"], self.sectors["Sector"])) if not self.sectors.empty else {}
        signals = []

        for symbol in symbols:
            candles = market_data.get(symbol)
            if candles is None or candles.empty:
                continue
            ref = reference_by_symbol.get(symbol)
            if not ref:
                continue
            sector = str(sector_map.get(symbol, "UNKNOWN"))
            sector_direction = sector_directions.get(sector, "UNKNOWN")
            if sector_direction == "UNKNOWN":
                continue
            signal = self.strategy.build(
                symbol=symbol,
                candles=candles,
                pdc=ref.get("PDC"),
                previous_day_open=ref.get("PreviousDayOpen"),
                sector_direction=sector_direction,
                nifty_direction=nifty_direction,
            )
            if signal:
                signal["sector"] = sector
                signal["market_direction"] = nifty_direction
                signal["stock_previous_day_direction"] = ref.get("PreviousDayDirection")
                signals.append(signal)
                print("SIGNAL:", symbol, signal["signal"], "Entry", signal["entry"], "SL", signal["stop_loss"], "Target", signal["target"])

        print("Final signals:", len(signals))
        return signals
