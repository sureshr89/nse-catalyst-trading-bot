# NSE Catalyst Trading Bot

## Active strategy — NIFTY 500 PDH/PDL + Today's Open Reversal

A Python-based **paper-trading** scanner for the **NIFTY 500 universe**. The active strategy uses previous-day High/Low, today's Open, completed 1-minute candles, NIFTY market direction and stock direction.

### SELL setup

1. Today's Open is **below PDL**.
2. Price first **reaches PDL from below**.
3. The PDL interaction must happen before the trigger candle.
4. A completed **1-minute candle opens above today's Open and closes below today's Open**.
5. The completed candle is the **trigger**; its close is not the execution price.
6. Enter using the **latest available market price after the trigger**.
7. NIFTY direction must be **BEARISH**.
8. Stock direction must be **BEARISH**.
9. Stop-loss = **today's High at the time of the setup**.
10. Target = **1.25 × actual risk**.

### BUY setup

1. Today's Open is **above PDH**.
2. Price first **reaches PDH from above**.
3. The PDH interaction must happen before the trigger candle.
4. A completed **1-minute candle opens below today's Open and closes above today's Open**.
5. The completed candle is the **trigger**; its close is not the execution price.
6. Enter using the **latest available market price after the trigger**.
7. NIFTY direction must be **BULLISH**.
8. Stock direction must be **BULLISH**.
9. Stop-loss = **today's Low at the time of the setup**.
10. Target = **1.25 × actual risk**.

### Risk controls

- Universe: **NIFTY 500**
- Starting paper capital: **₹2,50,000**
- Maximum risk per trade: **₹1,500**
- Required actual risk: **₹1,400–₹1,500**
- Minimum risk/reward: **1:1.25**
- Maximum 1 trade per stock per day
- Maximum 2 open positions
- Entry window: **09:45–14:00 IST**
- Mandatory square-off: **15:00 IST**
- Paper trading: **ON**
- Live trading: **OFF**

### Clean data model

Only the active strategy's data is retained in the runtime model: **PDH, PDL, today's Open, today's High/Low, 1-minute trigger information, NIFTY/stock direction, liquidity, risk and trade results**. Old setup fields are not part of the active model.

### Main modules

- `scanner/scanner_engine.py` — NIFTY 500 scanning and diagnostics
- `strategy/open_reversal_engine.py` — active PDH/PDL + Open reversal logic
- `strategy/risk_engine.py` — risk approval and position sizing
- `market/price_data.py` — NIFTY 500 and NIFTY market price data
- `data/stock_universe.py` — NIFTY 500 universe
- `data/reference_store.py` — PDH/PDL daily references
- `bot_runner.py` — persistent paper worker
- `dashboard/` — status, current trading, analysis and downloads

The repository is reset around this active strategy. Historical strategy output files are cleared before the new paper-trading journal begins.
