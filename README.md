# NSE Catalyst Trading Bot

## Current strategy — Gap-Failure + Open-Reclaim

A Python-based **paper-trading** bot for the **NIFTY 100** universe. The strategy is pure price action and does not use technical indicators.

### BUY setup

1. Previous trading day closed **green** (previous-day Close > previous-day Open).
2. Today opens **above PDC** (gap-up).
3. During today’s session, price trades **below PDC**.
4. NIFTY 100 direction is **BULLISH**.
5. The stock's sector direction is **BULLISH**.
6. After the PDC failure, a completed **1-minute candle closes back above today’s Open**.
7. BUY at that completed 1-minute candle close.
8. Stop-loss = **today’s session Low**.
9. Target = **1.5 × risk**.

### SELL setup

1. Previous trading day closed **red** (previous-day Close < previous-day Open).
2. Today opens **below PDC** (gap-down).
3. During today’s session, price trades **above PDC**.
4. NIFTY 100 direction is **BEARISH**.
5. The stock's sector direction is **BEARISH**.
6. After the PDC failure, a completed **1-minute candle closes back below today’s Open**.
7. SELL at that completed 1-minute candle close.
8. Stop-loss = **today’s session High**.
9. Target = **1.5 × risk**.

## Risk management

- Capital: ₹2,50,000
- Maximum risk per trade: ₹1,500
- Risk/reward: **1:1.5**
- Maximum 1 trade per stock per day
- Maximum 2 open positions
- Entry window: **09:45–14:00 IST**
- Mandatory square-off: **15:00 IST**
- Paper trading: **ON**
- Live trading: **OFF**

## Reference data

Before trading, the bot stores the latest completed trading day's PDC, previous-day Open and previous-day direction for the NIFTY 100 universe. PDC is the key previous-day price level used by the setup.

## Current architecture

- `scanner/scanner_engine.py` — NIFTY 100 scanning and alignment
- `strategy/gap_reclaim_engine.py` — active price-action strategy
- `strategy/risk_engine.py` — risk approval and position sizing
- `market/price_data.py` — market data
- `data/reference_store.py` — daily PDC/reference storage
- `bot_runner.py` — persistent Streamlit paper worker
- `dashboard/app.py` — Streamlit dashboard

The obsolete 5-minute pullback/frozen-high/frozen-low strategy has been removed from the repository so it cannot accidentally be used again.
