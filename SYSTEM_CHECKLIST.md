# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-14

## 1. Runtime / worker

- [x] `worker_service.py` — independent worker process, PID/heartbeat and singleton lock.
- [x] `bot_runner.py` — weekday loop, opening preparation, 09:45 entry window, 14:00 last entry, 15:00 square-off.
- [x] `main.py` — scanner → risk → paper execution → journal flow.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data finalized after square-off.

## 2. Market data / universe

- [x] `data/stock_universe.py` — NIFTY 500 universe loading.
- [x] `data/reference_store.py` — previous close, PDH, PDL and turnover reference data.
- [x] `data/sector_store.py` — sector classification with weekly cache/fallback.
- [x] `market/price_data.py` — 1-minute data cleaned to completed candles for scanner/position management.
- [x] Scan cadence aligned to one completed 1-minute bar (`60s`) to reduce redundant data requests.

## 3. Strategy

- [x] `strategy/open_reversal_engine.py` — PDH/PDL reaction + Open reversal.
- [x] PDH/PDL touch may occur after the 09:15 open and before 09:45.
- [x] Reversal candle must occur from 09:45 to 14:00.
- [x] Only the freshest qualifying reversal is considered.
- [x] Trigger older than 2 minutes is rejected, preventing late entries.
- [x] BUY: Open below PDL → PDL reaction → 1-minute candle opens below Open and closes above Open.
- [x] SELL: Open above PDH → PDH reaction → 1-minute candle opens above Open and closes below Open.
- [x] SL uses high/low available through the trigger candle, avoiding later-price look-ahead.
- [x] Target uses 1.25R.
- [x] Alignment controls are centralized in the scanner.

## 4. Scanner

- [x] `scanner/scanner_engine.py` — NIFTY 500 scan pipeline.
- [x] Gap board is built before liquidity filtering, so valid NIFTY 500 stocks can appear in gap-up/gap-down preparation.
- [x] Liquidity remains a trade-candidate filter.
- [x] NIFTY → sector → stock alignment is applied before final signals.
- [x] Scanner diagnostics record filter counts and rejection reasons.

## 5. Risk / execution

- [x] `strategy/risk_engine.py` — risk, R:R, capital, trade count and daily limits.
- [x] `papertrade/paper_trade_engine.py` — paper-only execution, SL, target and square-off.
- [x] `papertrade/trade_journal.py` — trade and signal records.
- [x] `papertrade/missed_capital_tracker.py` — capital-blocked setups monitored for research.
- [x] Actual market entry is separated from trigger-candle price.
- [x] Trigger identity is stable, preventing repeated processing of the same setup.

## 6. Dashboard

- [x] `dashboard/app.py` — live status and worker watchdog.
- [x] `dashboard/pages/current_trading.py` — live auto-refresh, gap board, positions, diagnostics and latest trade.
- [x] `dashboard/pages/analysis.py` + `dashboard/analysis.py` — analysis tabs and worker availability.
- [x] `dashboard/pages/downloads.py` — six-month table and month-wise Excel downloads.
- [x] Charts use static Plotly mode with zoom/drag/pinch disabled.
- [x] Daily reminder uses India calendar date.
- [x] Mobile bottom spacing added.

## 7. Master data

- [x] `master_data.py` — daily stock inputs, trades and daily summary.
- [x] Rolling retention is limited to current month + previous five months.
- [x] Daily summary uses entry date for trade activity and exit date for realized P&L.
- [x] Monthly Excel contains Daily Stock Inputs, All Trades, Daily Summary, Gap Board, Signals and README.
- [x] Gap Board sheet uses historical master stock inputs rather than only the current day's gap file.

## 8. Persistence / security

- [x] Runtime persistence branch is separate from `main`, preventing runtime commits from redeploying the code branch.
- [x] Public GitHub repositories are blocked from receiving runtime trading data by default.
- [ ] Google Drive/private external persistence — **not connected yet**.
- [ ] If GitHub persistence is desired, use a private repository or explicitly configure a private external storage method.

## 9. Automated checks

- [x] GitHub Actions compiles every Python file.
- [x] Core pytest suite covers risk approval, invalid stops, strategy SL/target, paper P&L and six-month retention.
- [x] Latest completed CI run before the final persistence-guard commit passed compile + core tests; a new CI run is triggered by the latest commit.

## 10. Final paper-trading flow

`09:15 market open`
→ `opening gap/reference preparation`
→ `gap-up / gap-down board ready before 09:45`
→ `09:45–14:00 fresh 1-minute reversal scan`
→ `NIFTY alignment`
→ `sector alignment`
→ `stock alignment`
→ `actual market entry`
→ `risk approval`
→ `paper position`
→ `SL / 1.25R target / 15:00 square-off`
→ `journal + master data`
→ `analysis + monthly download`
