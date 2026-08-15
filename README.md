# NSE Catalyst Trading Bot

## Active strategy — NIFTY 500 PDH/PDL + Today's Open Return

A Python-based **paper-trading** scanner for the **NIFTY 500 universe**. The active strategy uses previous-day High/Low, today's Open, completed 1-minute CLOSE data for setup detection, and the NIFTY 500 market filter.

### BUY setup

1. Activate the BUY side when NIFTY 500 is **≥ +0.25%** versus the previous trading close.
2. Build the BUY candidate pool from stocks where **Today's Open > PDH**.
3. Maintain those candidates in the waiting list using completed 1-minute **Close** prices.
4. When a candidate's Close goes **below PDH**, mark `PDH_BREACHED` and keep waiting.
5. When a breached candidate's Close returns to/reaches **Today's Open**, mark it **BUY QUALIFIED**.
6. No separate reversal-candle Open/Close pattern is required.
7. For qualified candidates, rank **ATR% → RVOL → Beta → traded value**.
8. Immediately before entry, re-check NIFTY 500 ≥ +0.25% and the stock is at/above Today's Open.
9. Use the current available market price as the entry price.
10. Stop-loss = **PDH**; target = **1.25R**.

### SELL setup

1. Activate the SELL side when NIFTY 500 is **≤ −0.25%** versus the previous trading close.
2. Build the SELL candidate pool from stocks where **Today's Open < PDL**.
3. Maintain those candidates in the waiting list using completed 1-minute **Close** prices.
4. When a candidate's Close goes **above PDL**, mark `PDL_BREACHED` and keep waiting.
5. When a breached candidate's Close returns to/reaches **Today's Open**, mark it **SELL QUALIFIED**.
6. No separate reversal-candle Open/Close pattern is required.
7. For qualified candidates, rank **ATR% → RVOL → Beta → traded value**.
8. Immediately before entry, re-check NIFTY 500 ≤ −0.25% and the stock is at/below Today's Open.
9. Use the current available market price as the entry price.
10. Stop-loss = **PDL**; target = **1.25R**.

### Runtime and data flow

- Market setup data: completed **1-minute** data.
- Control cycle: **30 seconds**.
- Market-data refresh/cache: approximately **60 seconds**.
- Waiting and qualified candidate states persist between cycles; the bot does not restart the setup from zero each cycle.
- Once a stock is finalized for entry, entry/risk/SL/target are calculated immediately rather than waiting for another control cycle.

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
- ATR%, RVOL, Beta and traded value **rank already-qualified candidates only**; they do not create a trade by themselves.

### Main modules

- `scanner/scanner_engine.py` — NIFTY 500 scanning, waiting states, qualification and ranking
- `strategy/open_reversal_engine.py` — PDH/PDL + Today's Open state logic
- `strategy/candidate_metrics.py` — ATR%, RVOL, Beta and traded-value ranking metrics
- `strategy/risk_engine.py` — risk approval, position sizing and daily worst-case loss protection
- `market/price_data.py` — NIFTY 500 and NIFTY market price data
- `market/live_price.py` — fresh available 1-minute market price for paper entry
- `data/stock_universe.py` — NIFTY 500 universe
- `data/reference_store.py` — PDH/PDL daily references
- `bot_runner.py` — persistent paper worker
- `dashboard/` — status, current trading, analysis, stock scanner and downloads

The application remains paper-trading only. Live order execution is explicitly disabled.
