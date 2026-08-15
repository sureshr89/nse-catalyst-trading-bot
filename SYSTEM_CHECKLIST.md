# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-15

## 1. Runtime / worker
- [x] `bot_runner.py` — weekday loop, pre-entry preparation, 09:45 entry start, 14:00 last entry, 15:00 square-off.
- [x] `main.py` — scanner → risk → paper execution → journal flow.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data finalized after square-off.

## 2. Market data / universe
- [x] `data/stock_universe.py` — NIFTY 500 universe with minimum coverage protection.
- [x] `data/reference_store.py` — previous close, PDH and PDL reference data.
- [x] `market/price_data.py` — completed 1-minute data in IST; forming minute is rejected.
- [x] Universe scan requires at least 95% synchronized 1-minute coverage.
- [x] NIFTY 500 index must have the same completed minute for the market filter.

## 3. Exact strategy
- [x] Strategy uses completed **1-minute price records** for the reversal trigger.
- [x] Gap Up means `Today's Open > PDH`.
- [x] Gap Down means `Today's Open < PDL`.
- [x] BUY sequence: Open > PDH → price closes below PDH → later trigger candle opens below Today's Open and closes above Today's Open.
- [x] SELL sequence: Open < PDL → price closes above PDL → later trigger candle opens above Today's Open and closes below Today's Open.
- [x] Trigger must be fresh within `MAX_TRIGGER_AGE_MINUTES`.
- [x] Entry price is the trigger candle close.
- [x] BUY SL = PDH.
- [x] SELL SL = PDL.
- [x] Target = 1.25 × actual entry-to-SL risk.
- [x] NIFTY 500 filter: BUY `>= +0.25%`; SELL `<= -0.25%` versus previous trading close.
- [x] Industry/Sector is not a strategy condition.
- [x] There is no separate stock-direction alignment filter.
- [x] Entry window is `09:45–14:00 IST`.

## 4. Scanner
- [x] `scanner/scanner_engine.py` scans the NIFTY 500 universe from synchronized 1-minute data.
- [x] Today's Open is taken from the first market 1-minute record and remains fixed for the session.
- [x] Gap board is PDH/PDL-relative; previous-close gap is retained as informational data.
- [x] No sector/industry filter.
- [x] No EMA, VWAP, BOS/CHOCH, FVG or unrelated pattern filter.
- [x] NIFTY 500 percentage filter is applied before final signals.
- [x] Diagnostics record coverage, gap counts, market filter and final signals.

## 5. Risk / execution
- [x] Maximum risk per trade = ₹1,500.
- [x] Required actual risk = ₹1,400–₹1,500.
- [x] Maximum 2 open positions.
- [x] Daily maximum loss = ₹3,000.
- [x] Daily worst-case protection includes realized P&L + existing open-position risk + proposed new risk.
- [x] Minimum R:R = 1:1.25.
- [x] Maximum 1 trade per stock per day.
- [x] Paper execution validates the same entry/SL/target/risk rules again before opening.
- [x] 15:00 square-off remains mandatory.

## 6. Dashboard
- [x] `dashboard/app.py` — Bot Status and exact strategy conditions.
- [x] `dashboard/pages/current_trading.py` — current gap candidates, approved signals and open positions.
- [x] `dashboard/pages/analysis.py` — concise historical performance analysis.
- [x] `dashboard/pages/stock_scanner.py` — stock-by-stock status; Industry is information only.
- [x] `dashboard/pages/downloads.py` — trades, signals, gap board and monthly master workbook.
- [x] Obsolete duplicate `dashboard/analysis.py` removed.

## 7. Journal / persistence
- [x] Active journal stores only fields required by the current strategy and execution state.
- [x] Approved and rejected scanner/risk decisions can be recorded with their reason.
- [x] Paper-state persistence version is aligned with the paper execution engine.
- [x] Future/unknown paper-state versions are quarantined rather than overwritten.
- [x] Signal history is deduplicated by stock, side, setup and trigger time.

## 8. Master data
- [x] `master_data.py` stores daily stock inputs, trades and daily summary.
- [x] Gap counts use `GAP_UP` / `GAP_DOWN`.
- [x] NIFTY 500 percentage change is stored in the daily summary.
- [x] Rolling retention remains six months.
- [x] Monthly Excel keeps Daily Stock Data, All Trades, Daily Summary, Gap Board, Signals and README.

## 9. Automated checks
- [x] GitHub Actions compiles every Python file.
- [x] Core import checks run after compilation succeeds.
- [ ] Final live-market workflow test — to be performed separately after code audit.

## 10. Final paper-trading flow

`09:15 market open`
→ `Today's Open + PDH + PDL`
→ `identify Gap Up / Gap Down`
→ `synchronized completed 1-minute prices`
→ `BUY: close below PDH → later candle opens below Open and closes above Open`
→ `SELL: close above PDL → later candle opens above Open and closes below Open`
→ `NIFTY 500 ±0.25% filter`
→ `risk + capital + daily worst-case-loss gate`
→ `paper entry at trigger close`
→ `BUY SL=PDH / SELL SL=PDL`
→ `1.25R target`
→ `14:00 no new entries`
→ `15:00 square-off`
→ `journal + master data + analysis + downloads`
