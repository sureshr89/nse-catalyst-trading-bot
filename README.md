# NSE Catalyst Trading Bot

## Current strategy — NIFTY 500 PDH/PDL + Today's Open 1-minute Cross

A Python-based **paper-trading** bot for the **NIFTY 500 scanner universe**. The strategy is pure price action and uses previous-day High/Low, today's Open, 1-minute candles, market direction, sector direction and stock direction.

### SELL setup

1. Today's Open is **above PDH (Previous Day High)**.
2. Price first **comes down to/touches PDH**.
3. The PDH interaction must happen **before** the trigger candle.
4. Price then moves back through today's Open.
5. A completed **1-minute candle opens above today's Open and closes below today's Open**.
6. That candle close is the **trigger**, not the execution price.
7. Enter at the **latest available market price immediately after the completed trigger candle**.
8. NIFTY market direction must be **BEARISH** when market alignment is enabled.
9. Sector direction must be **BEARISH** when sector alignment is enabled.
10. Stock current-day direction must be **BEARISH** when stock alignment is enabled.
11. Stop-loss = **today's session High**.
12. Target = **1.25 × actual risk**.

### BUY setup

1. Today's Open is **below PDL (Previous Day Low)**.
2. Price first **comes up to/touches PDL**.
3. The PDL interaction must happen **before** the trigger candle.
4. Price then moves back through today's Open.
5. A completed **1-minute candle opens below today's Open and closes above today's Open**.
6. That candle close is the **trigger**, not the execution price.
7. Enter at the **latest available market price immediately after the completed trigger candle**.
8. NIFTY market direction must be **BULLISH** when market alignment is enabled.
9. Sector direction must be **BULLISH** when sector alignment is enabled.
10. Stock current-day direction must be **BULLISH** when stock alignment is enabled.
11. Stop-loss = **today's session Low**.
12. Target = **1.25 × actual risk**.

### Risk management

- Scanner universe: **NIFTY 500**
- Capital: ₹2,50,000
- Maximum risk per trade: ₹1,500
- Accepted actual risk band: **₹1,400–₹1,500**
- Risk/reward: **minimum 1:1.25**
- Maximum 1 trade per stock per day
- Maximum 2 open positions
- Entry window: **09:45–14:00 IST**
- Mandatory square-off: **15:00 IST**
- Paper trading: **ON**
- Live trading: **OFF**

### Reference data

Before trading, the bot stores the latest completed trading day's **PDH, PDL, PDC, Open and turnover** for the NIFTY 500 universe. PDH/PDL are the structural reference levels used by the strategy.

### Architecture

- `scanner/scanner_engine.py` — NIFTY 500 scanning and filter diagnostics
- `strategy/pdh_pdl_open_cross_engine.py` — active PDH/PDL + Open Cross strategy
- `strategy/risk_engine.py` — risk approval and position sizing
- `market/price_data.py` — market data
- `data/stock_universe.py` — NIFTY 500 universe
- `data/reference_store.py` — PDH/PDL/PDC daily references
- `data/sector_store.py` — sector mapping
- `bot_runner.py` — persistent paper worker
- `dashboard/app.py` — Streamlit dashboard
- `dashboard/pages/current_trading.py` — live positions and scanner breakdown
- `dashboard/pages/analysis.py` — read-only trade analysis
- `dashboard/pages/downloads.py` — trading and NIFTY 500 research downloads

The previous Gap-Failure + Open-Reclaim strategy and its historical paper-trade data have been reset/removed from the active repository state.
