# NSE Catalyst Trading Bot

## Current strategy — NIFTY 250 Gap-Failure + Open-Reclaim

A Python-based **paper-trading** bot for the **NIFTY 250 scanner universe**, defined as **NIFTY 100 + NIFTY Midcap 150**. The strategy is pure price action and does not use technical indicators.

### BUY setup

1. Previous trading day closed **green** (previous-day Close > previous-day Open).
2. Today opens **above PDC** (gap-up).
3. During today's session, price trades **below PDC**.
4. NIFTY 100 market direction is **BULLISH**.
5. The stock's sector direction is **BULLISH**.
6. The stock's own current-day direction is aligned **BULLISH** and its previous-day direction is aligned with the setup.
7. After the PDC failure, a completed **1-minute candle closes back above today's Open**.
8. BUY at that completed 1-minute candle close.
9. Stop-loss = **today's session Low**.
10. Target = **1.25 × risk**.

### SELL setup

1. Previous trading day closed **red** (previous-day Close < previous-day Open).
2. Today opens **below PDC** (gap-down).
3. During today's session, price trades **above PDC**.
4. NIFTY 100 market direction is **BEARISH**.
5. The stock's sector direction is **BEARISH**.
6. The stock's own current-day direction is aligned **BEARISH** and its previous-day direction is aligned with the setup.
7. After the PDC failure, a completed **1-minute candle closes back below today's Open**.
8. SELL at that completed 1-minute candle close.
9. Stop-loss = **today's session High**.
10. Target = **1.25 × risk**.

### Risk management

- Scanner universe: **NIFTY 250 = NIFTY 100 + NIFTY Midcap 150**
- Capital: ₹2,50,000
- Maximum risk per trade: ₹1,500
- **Accepted actual risk band: ₹1,400–₹1,500 only**
- Risk/reward: **minimum 1:1.25**
- Maximum 1 trade per stock per day
- Maximum 2 open positions
- Entry window: **09:45–14:00 IST**
- Mandatory square-off: **15:00 IST**
- Paper trading: **ON**
- Live trading: **OFF**

A stock is rejected if whole-share sizing cannot produce actual risk within ₹1,400–₹1,500 without exceeding ₹1,500. The bot never increases quantity beyond the ₹1,500 cap just to reach the minimum risk.

## Reference data

Before trading, the bot stores the latest completed trading day's PDC, previous-day Open and previous-day direction for the NIFTY 250 scanner universe. PDC is the key previous-day price level used by the setup.

## Current architecture

- `scanner/scanner_engine.py` — NIFTY 250 scanning with NIFTY 100 market, sector and stock alignment
- `strategy/gap_reclaim_engine.py` — active price-action strategy
- `strategy/risk_engine.py` — risk approval and position sizing
- `market/price_data.py` — market data
- `data/stock_universe.py` — NIFTY 100 + NIFTY Midcap 150 universe
- `data/reference_store.py` — daily PDC/reference storage
- `data/sector_store.py` — NIFTY 250 sector mapping
- `bot_runner.py` — persistent paper worker
- `dashboard/app.py` — Streamlit dashboard
- `dashboard/pages/current_trading.py` — live positions and scanner breakdown
- `dashboard/pages/analysis.py` — read-only trade analysis
- `dashboard/pages/downloads.py` — trading and NIFTY 250 research downloads
- `outputs/signals.csv` — scanner decision journal
- `outputs/trades.csv` — trade execution/journal

The obsolete 5-minute pullback/frozen-high/frozen-low strategy has been removed from the repository so it cannot accidentally be used again.
