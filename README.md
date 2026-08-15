# NSE Catalyst Trading Bot

## Active strategy — NIFTY 500 PDH/PDL + Today's Open Reversal

A Python-based **paper-trading** scanner for the **NIFTY 500 universe**. The active strategy uses previous-day High/Low, today's Open, completed 1-minute price data and the NIFTY 500 market filter.

### BUY setup

1. Today's Open is **above PDH**.
2. A completed 1-minute price record must show price **below PDH** after the Open setup.
3. After that breach, a later completed 1-minute trigger candle must **open below Today's Open and close above Today's Open**.
4. The trigger must be fresh within the configured trigger-age window.
5. NIFTY 500 must be **≥ +0.25%** versus the previous trading close.
6. Entry price = the trigger candle **close**.
7. Stop-loss = **PDH**.
8. Target = **1.25 × entry-to-SL risk**.

### SELL setup

1. Today's Open is **below PDL**.
2. A completed 1-minute price record must show price **above PDL** after the Open setup.
3. After that breach, a later completed 1-minute trigger candle must **open above Today's Open and close below Today's Open**.
4. The trigger must be fresh within the configured trigger-age window.
5. NIFTY 500 must be **≤ −0.25%** versus the previous trading close.
6. Entry price = the trigger candle **close**.
7. Stop-loss = **PDL**.
8. Target = **1.25 × entry-to-SL risk**.

### Risk controls

- Universe: **NIFTY 500**
- Starting paper capital: **₹2,50,000**
- Maximum risk per trade: **₹1,500**
- Required actual risk: **₹1,400–₹1,500**
- Minimum risk/reward: **1:1.25**
- Maximum 1 trade per stock per day
- Maximum 2 open positions
- Maximum daily loss: **₹3,000**
- Daily profit target: **₹5,000**
- Entry window: **09:45–14:00 IST**
- Mandatory square-off: **15:00 IST**
- Paper trading: **ON**
- Live trading: **OFF**

### What is NOT a strategy condition

- **Industry/Sector is not a trading filter.**
- There is no separate stock-direction alignment filter.
- No EMA, VWAP, BOS/CHOCH, FVG or other technical-pattern filter is used.
- The gap board is informational/setup preparation; final entry requires the exact reversal sequence above.

### Main modules

- `scanner/scanner_engine.py` — NIFTY 500 scanning and diagnostics
- `strategy/open_reversal_engine.py` — active PDH/PDL + Today's Open reversal logic
- `strategy/risk_engine.py` — risk approval, position sizing and daily worst-case loss protection
- `market/price_data.py` — NIFTY 500 and NIFTY market price data
- `data/stock_universe.py` — NIFTY 500 universe
- `data/reference_store.py` — PDH/PDL daily references
- `bot_runner.py` — persistent paper worker
- `dashboard/` — status, current trading, analysis, stock scanner and downloads

The application remains paper-trading only. Live order execution is explicitly disabled.
