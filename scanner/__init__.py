"""Scanner package compatibility/coverage policy patch.

The live S1/S2 workflow must not reject the entire NIFTY 500 scan merely because
Yahoo 1-minute data is temporarily unavailable for a large portion of the universe.
The universe/opening reference scan remains NIFTY 500; 1-minute data is used only
where available for live strategy state transitions.
"""

# Keep this compatibility patch small and isolated so the strategy rules themselves
# are unchanged. scanner_engine historically hard-coded a 60% universe 1m coverage
# gate; that gate made S1/S2 stop completely when Yahoo returned partial 1m data.
try:
    import importlib

    _scanner_engine = importlib.import_module("scanner.scanner_engine")
    _scanner_engine.MIN_MARKET_DATA_COVERAGE = 0.10
except Exception:
    # Normal import errors must still surface from scanner_engine itself.
    pass
