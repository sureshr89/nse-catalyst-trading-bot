"""Market data package initialization."""

# Market modules are imported explicitly by the active scanner. Keep this
# initializer side-effect free so importing ``market`` cannot trigger stale
# strategy modules or monkey-patch yfinance globally.
