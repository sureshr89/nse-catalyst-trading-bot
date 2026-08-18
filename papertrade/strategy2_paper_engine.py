"""Isolated paper engine for Strategy 2 with its own capital/state file."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import (
    PAPER_TRADING, LIVE_TRADING, TRADING_START, LAST_ENTRY_TIME, SQUARE_OFF_TIME,
    MARKET_CLOSE, MAX_OPEN_POSITIONS, MIN_REQUIRED_RISK, MAX_RISK_PER_TRADE,
    MIN_RR_RATIO, STRATEGY2_TOTAL_CAPITAL,
)
from papertrade.paper_trade_engine import PaperTradeEngine
from market.price_data import PriceData

INDIA_TZ = ZoneInfo("Asia/Kolkata")
STRATEGY2_CAPITAL = float(STRATEGY2_TOTAL_CAPITAL)


class Strategy2PaperTradeEngine(PaperTradeEngine):
    """Paper execution isolated from Strategy 1's configured Strategy 2 capital/state."""

    def __init__(self):
        self.paper_trading = bool(PAPER_TRADING)
        self.live_trading = bool(LIVE_TRADING)
        self.trading_start = TRADING_START
        self.last_entry_time = LAST_ENTRY_TIME
        self.square_off_time = SQUARE_OFF_TIME
        self.market_close = MARKET_CLOSE
        self.open_positions = {}
        self.closed_positions = []
        self.trade_counter = 0
        self.total_capital = STRATEGY2_CAPITAL
        self.available_capital = STRATEGY2_CAPITAL
        self.used_capital = 0.0
        self.price_data = PriceData()
        self._restore_state()

    def _state_path(self):
        return str(Path("outputs") / "strategy2_paper_engine_state.json")

    def _save_state(self):
        path_obj = Path(self._state_path())
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "state_version": 2,
            "strategy": "GAP_EXTENSION_REVERSAL_BUY_SELL",
            "session_date": datetime.now(INDIA_TZ).date().isoformat(),
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "trade_counter": self.trade_counter,
            "total_capital": self.total_capital,
            "available_capital": self.available_capital,
            "used_capital": self.used_capital,
            "saved_at": datetime.now(INDIA_TZ).isoformat(),
        }
        try:
            import json
            path_obj.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception as error:
            print(f"Strategy 2 paper state save skipped: {type(error).__name__}: {error}")
