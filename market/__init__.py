"""Market data package initialization."""

# Install the Yahoo reliability layer before market modules import yfinance.
from . import yahoo_patch  # noqa: F401,E402
