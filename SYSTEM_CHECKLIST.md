# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-15

## 1. Runtime / worker
- [x] `bot_runner.py` — weekday loop, pre-entry preparation, 09:45 entry start, 14:00 last entry, 15:00 square-off.
- [x] `main.py` — scanner → risk → paper execution → journal flow.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data finalized after square-off.

## 2. Market data / universe
- [x] `data/stock_universe.py` — NIFTY 500 universe.
- [x] `data/reference_store.py` — previous close, PDH, PDL and turnover reference data.
- [x] `market/price_data.py` — current completed 1-minute data in IST; forming minute is rejected.
- [x] Universe scan requires at least 95% current/synchronized 1-minute coverage (about 475 of 500 when the universe contains 500 stocks).
- [x] NIFTY 500 index must have the same synchronized completed minute.

## 3. Exact strategy
- [x] Strategy uses **1-minute prices only**; no candlestick-pattern confirmation.
- [x] Gap Up means `Today's Open > PDH`.
- [x] Gap Down means `Today's Open < PDL`.
- [x] BUY uses **PDH only**. PDL is not a BUY condition.
- [x] SELL uses **PDL only**. PDH is not a SELL condition.
- [x] BUY sequence: Open > PDH → price goes below PDH → price later returns to/reaches Today's Open → BUY.
- [x] SELL sequence: Open < PDL → price goes above PDL → price later returns to/reaches Today's Open → SELL.
- [x] Entry price is the **current 1-minute market price at the return/cross**, not an assumed candle close at Today's Open.
- [x] BUY SL = PDH.
- [x] SELL SL = PDL.
- [x] BUY target = `Entry + (Entry - PDH) × 1.25`.
- [x] SELL target = `Entry - (PDL - Entry) × 1.25`.
- [x] NIFTY 500 filter: BUY requires `>= +0.25%`; SELL requires `<= -0.25%` versus previous trading close.
- [x] Entry window is evaluated in `Asia/Kolkata`: 09:45–14:00 IST.

## 4. Scanner
- [x] `scanner/scanner_engine.py` scans the NIFTY 500 universe from current 1-minute data.
- [x] Today's Open is taken from the first market 1-minute record and then treated as the fixed session Open.
- [x] Gap board is PDH/PDL-relative; previous-close gap is retained as a separate field.
- [x] No stock candle-direction filter.
- [x] No EMA, VWAP, BOS/CHOCH, FVG or other pattern confirmation.
- [x] NIFTY 500 percentage filter is applied before final signals.
- [x] Diagnostics record coverage, gap counts, market filter and final signals.

## 5. Risk / execution
- [x] `strategy/risk_engine.py` keeps existing capital, risk, R:R, per-stock and daily limits.
- [x] `papertrade/paper_trade_engine.py` remains paper-only and manages SL, target and 15:00 square-off.
- [x] Existing repeated-1-minute-record protection remains in position management.
- [x] Actual entry price, PDH/PDL stop and calculated target are stored in the trade journal.
- [x] Existing cooldown, max-position and daily P&L controls remain unchanged.

## 6. Dashboard
- [x] `dashboard/app.py` — Bot Status shows the exact strategy conditions.
- [x] `dashboard/pages/current_trading.py` — current 1-minute market data, gap board, live position price, NIFTY 500 filter and diagnostics.
- [x] `dashboard/pages/analysis.py` + `dashboard/analysis.py` — existing analysis retained.
- [x] `dashboard/pages/downloads.py` — strategy-specific gap board, trades, signals, diagnostics and monthly master workbook.

## 7. Master data
- [x] `master_data.py` — daily stock inputs, trades and daily summary.
- [x] Gap counts use `GAP_UP` / `GAP_DOWN`.
- [x] NIFTY 500 percentage change is stored in the daily summary.
- [x] Rolling retention remains six months.
- [x] Monthly Excel keeps Daily Stock Inputs, All Trades, Daily Summary, Gap Board, Signals and README.

## 8. Automated checks
- [x] GitHub Actions compiles every Python file.
- [x] Core import checks run in GitHub Actions.

## 9. Final paper-trading flow

`09:15 market open`
→ `Today's Open + PDH + PDL`
→ `identify Gap Up / Gap Down`
→ `current 1-minute prices`
→ `BUY: below PDH → return to Open`
→ `SELL: above PDL → return to Open`
→ `NIFTY 500 ±0.25% filter`
→ `actual market-price entry`
→ `BUY SL=PDH / SELL SL=PDL`
→ `1.25R target`
→ `14:00 no new entries`
→ `15:00 square-off`
→ `journal + master data + analysis + downloads`
