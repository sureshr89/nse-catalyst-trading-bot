"""Market data package initialization."""

# Install the Yahoo reliability layer before market modules import yfinance.
from . import yahoo_patch  # noqa: F401,E402

# A complete 250-stock breadth snapshot is expensive. Reuse it briefly while
# continuing to rescan individual stock setups each cycle.
import time

from .industry_direction import IndustryDirection

_INDUSTRY_CACHE_SECONDS = 45
_ORIGINAL_INDUSTRY_ANALYZE = IndustryDirection.analyze


def _cached_industry_analyze(self):
    now = time.monotonic()
    cached_at = getattr(self, "_nse_cache_time", 0.0)
    cached_value = getattr(self, "_nse_cache_value", None)

    if cached_value is not None and now - cached_at < _INDUSTRY_CACHE_SECONDS:
        return cached_value

    value = _ORIGINAL_INDUSTRY_ANALYZE(self)
    if value is not None:
        self._nse_cache_time = now
        self._nse_cache_value = value
    return value


IndustryDirection.analyze = _cached_industry_analyze
