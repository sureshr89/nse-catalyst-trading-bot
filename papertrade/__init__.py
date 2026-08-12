"""Paper-trading package.

Persistence is implemented directly by PaperTradeEngine and
papertrade.persistent_storage. This package initializer intentionally does
not monkey-patch engine methods or start background threads during import.
"""

from .paper_trade_engine import PaperTradeEngine
from .trade_journal import TradeJournal

__all__ = ["PaperTradeEngine", "TradeJournal"]
