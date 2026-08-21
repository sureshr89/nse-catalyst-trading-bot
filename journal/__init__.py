"""Canonical journal package for the clean NIFTY 500 S1-S5 paper strategy.

The implementation remains in :mod:`papertrade.trade_journal_clean` for
backward compatibility.  This package exposes the canonical TradeJournal
entry point so callers do not need to know the legacy module location.
"""

from papertrade.trade_journal_clean import TradeJournal

__all__ = ["TradeJournal"]
