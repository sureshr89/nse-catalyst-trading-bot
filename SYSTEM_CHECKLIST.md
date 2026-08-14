# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-15

## 1. Runtime / worker

- [x] `bot_runner.py` — weekday loop, opening preparation, 09:45 entry window, 14:00 last entry, 15:00 square-off.
- [x] `main.py` — scanner → risk → paper execution → journal flow.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data finalized after square-off.

## 2. Market data / universe

- [x] `data/stock_universe.py` — NIFTY 500 universe loading.
- [x] `data/reference_store.py` — previous close, PDH, PDL and turnover reference data.
- [x] `market/price_data.py` — 1-minute data cleaned to completed candles for scanner/position management.
- [x] Scan cadence aligned to one completed 1-minute bar (`60s`) to reduce redundant data requests.

## 3. Strategy

- [x] `strategy/open_reversal_engine.py` — PDH/PDL reaction + Open reversal.
- [x] PDH/PDL touch may occur after the 09:15 open and before 09:45.
- [x] Reversal candle must occur from 09:45 to 14:00.
- [x] Only the freshest qualifying reversal is considered.
- [x] Trigger older than 2 minutes is rejected, preventing late entries.
- [x] BUY: Open above PDH → PDH reaction → 1-minute candle opens below Open and closes above Open.
- [x] SELL: Open below PDL → PDL reaction → 1-minute candle opens above Open and closes below Open.
- [x] SL uses today's Low/High through the trigger setup.
- [x] Target uses 1.25R.
- [x] Alignment is NIFTY 500 direction + stock direction only.

## 4. Scanner

- [x] `scanner/scanner_engine.py` — NIFTY 500 scan pipeline.
- [x] Gap board is built before liquidity filtering.
- [x] Liquidity remains a trade-candidate filter.
- [x] NIFTY 500 market alignment is checked before final signals.
- [x] Stock alignment is checked before final signals.
- [x] No sector filter or sector analysis is used.
- [x] Scanner diagnostics record filter counts and rejection reasons.

## 5. Risk / execution

- [x] `strategy/risk_engine.py` — risk, R:R, capital, trade count and daily limits.
- [x] `papertrade/paper_trade_engine.py` — paper-only execution, SL, target and square-off.
- [x] Sector-free trade journal records market/stock alignment, risk and results.
- [x] `papertrade/missed_capital_tracker.py` — capital-blocked setups monitored for research.
- [x] Actual market entry is separated from trigger-candle price.
- [x] Trigger identity is stable, preventing repeated processing of the same setup.

## 6. Dashboard

- [x] `dashboard/app.py` — live status and worker watchdog.
- [x] `dashboard/pages/current_trading.py` — live auto-refresh, gap board, positions, NIFTY 500/stock alignment, diagnostics and latest trade.
- [x] `dashboard/pages/analysis.py` + `dashboard/analysis.py` — analysis tabs without sector analysis.
- [x] `dashboard/pages/downloads.py` — six-month table and month-wise Excel downloads without sector exports.
- [x] Charts use static Plotly mode with zoom/drag/pinch disabled.
- [x] Daily reminder uses India calendar date.
- [x] Mobile bottom spacing added.

## 7. Master data

- [x] `master_data.py` — daily stock inputs, trades and daily summary.
- [x] Rolling retention is limited to current month + previous five months.
- [x] Daily summary uses entry date for trade activity and exit date for realized P&L.
- [x] Monthly Excel contains Daily Stock Inputs, All Trades, Daily Summary, Gap Board, Signals and README.
- [x] No sector analysis sheet/export is generated.

## 8. Persistence / security

- [x] Runtime persistence branch is separate from `main`.
- [x] Public GitHub repositories are blocked from receiving runtime trading data by default.
- [ ] Google Drive/private external persistence — **not connected yet**.

## 9. Automated checks

- [x] GitHub Actions compiles every Python file.
- [x] Core tests cover risk approval, invalid stops, strategy SL/target, paper P&L and six-month retention.

## 10. Final paper-trading flow

`09:15 market open`
→ `opening gap/reference preparation`
→ `gap-up / gap-down board ready before 09:45`
→ `09:45–14:00 fresh 1-minute reversal scan`
→ `NIFTY 500 direction`
→ `stock alignment`
→ `liquidity`
→ `actual market entry`
→ `risk approval`
→ `paper position`
→ `SL / 1.25R target / 15:00 square-off`
→ `journal + master data`
→ `analysis + monthly download`
