# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-15

## 1. Runtime / worker
- [x] `bot_runner.py` — weekday loop, pre-entry preparation, 09:45 entry start, 14:00 last entry, 15:00 square-off.
- [x] `main.py` — scanner → risk → paper execution → journal flow.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data finalized after square-off.
- [x] Control cycle runs every 30 seconds.
- [x] Market setup data is refreshed/cached on the 1-minute cadence rather than rebuilt every 30-second cycle.

## 2. Market data / universe
- [x] `data/stock_universe.py` — NIFTY 500 universe with minimum coverage protection.
- [x] `data/reference_store.py` — previous close, PDH and PDL reference data.
- [x] `market/price_data.py` — completed 1-minute data in IST; forming minute is rejected.
- [x] Strategy-state detection uses the completed 1-minute **Close**; no separate reversal-candle Open/Close pattern is required.
- [x] Universe scan requires at least 95% synchronized 1-minute coverage.
- [x] NIFTY 500 index uses the latest completed 1-minute data for the market filter.

## 3. Exact strategy
- [x] BUY activates when NIFTY 500 `>= +0.25%`.
- [x] SELL activates when NIFTY 500 `<= -0.25%`.
- [x] BUY candidate: `Today's Open > PDH`.
- [x] SELL candidate: `Today's Open < PDL`.
- [x] BUY state: completed 1-minute Close below PDH → wait for Close to return to/reach Today's Open.
- [x] SELL state: completed 1-minute Close above PDL → wait for Close to return to/reach Today's Open.
- [x] Reaching Today's Open makes the stock **QUALIFIED**; no separate reversal candle is required.
- [x] Final entry re-checks the NIFTY 500 filter and stock price relative to Today's Open.
- [x] Final entry uses the current available market price, not the historical trigger candle close.
- [x] BUY SL = PDH.
- [x] SELL SL = PDL.
- [x] Target = 1.25 × actual entry-to-SL risk.
- [x] ATR%, RVOL, Beta and traded value rank already-qualified candidates only.
- [x] Ranking order: **ATR% → RVOL → Beta → traded value**.
- [x] Industry/Sector is not a strategy condition.
- [x] There is no separate stock-direction alignment filter.
- [x] Entry window is `09:45–14:00 IST`.

## 4. Scanner / state management
- [x] `scanner/scanner_engine.py` maintains BUY and SELL waiting dictionaries across 30-second cycles.
- [x] Candidates are added to the waiting list once their opening condition is identified; state then progresses instead of restarting the setup.
- [x] `PDH_BREACHED` / `PDL_BREACHED` state persists until Today's Open is reached or the session ends.
- [x] Qualified candidates are removed from waiting and placed in the qualified list.
- [x] Qualified candidates are ranked before execution.
- [x] Candidate identity prevents repeated entry of the same finalized setup.
- [x] Gap board is PDH/PDL-relative; previous-close gap remains informational.
- [x] No sector/industry filter.
- [x] No EMA, VWAP, BOS/CHOCH, FVG or unrelated pattern filter.
- [x] Diagnostics record coverage, waiting counts, qualified counts, ranking metrics and final signals.

## 5. Risk / execution
- [x] Maximum risk per trade = ₹1,500.
- [x] Required actual risk = ₹1,400–₹1,500.
- [x] Quantity is calculated from actual Entry-to-SL distance and available capital.
- [x] Maximum 2 open positions.
- [x] Daily maximum loss = ₹3,000.
- [x] Daily worst-case protection includes realized P&L + existing open-position risk + proposed new risk.
- [x] Minimum R:R = 1:1.25.
- [x] Maximum 1 trade per stock per day.
- [x] Paper execution validates the same entry/SL/target/risk rules again before opening.
- [x] Entry is triggered immediately after final qualification/risk approval; it does not wait for another 30-second cycle.
- [x] 15:00 square-off remains mandatory.

## 6. Dashboard
- [x] `dashboard/app.py` — Bot Status and exact strategy conditions.
- [x] `dashboard/pages/current_trading.py` — waiting stocks, qualified candidates, priority, approved signals and open positions.
- [x] `dashboard/pages/analysis.py` — historical performance analysis.
- [x] `dashboard/pages/stock_scanner.py` — stock-by-stock status, 2×2 workflow KPI cards, ranking metrics and waiting states.
- [x] `dashboard/pages/downloads.py` — trades, signals, gap board and monthly master workbook.
- [x] Shared dashboard styling keeps the responsive 2×2 metric layout.

## 7. Journal / persistence
- [x] Active journal stores current strategy and execution fields, including ATR%, RVOL, Beta and priority when available.
- [x] Approved and rejected scanner/risk decisions can be recorded with their reason.
- [x] Paper-state persistence version is aligned with the paper execution engine.
- [x] Future/unknown paper-state versions are quarantined rather than overwritten.
- [x] Signal history is deduplicated by candidate identity.

## 8. Master data / CSV outputs
- [x] `gap_analysis.csv` stores Symbol, Industry, PreviousClose, TodayOpen, PDH, PDL, gap fields and GapType.
- [x] `signals.csv` stores entry, SL, target, quantity/risk results, candidate state and ranking metrics when available.
- [x] `trades.csv` stores paper entry/exit, quantity, risk, target and strategy context.
- [x] `MASTER_DAILY_STOCK_DATA.csv`, `MASTER_TRADES.csv` and `MASTER_DAILY_SUMMARY.csv` are updated after the final square-off.
- [x] Rolling master retention remains six months.
- [x] Monthly Excel keeps Daily Stock Data, All Trades, Daily Summary, Gap Board, Signals and README.

## 9. Automated checks
- [x] GitHub Actions compiles every Python file.
- [x] Core import checks run after compilation succeeds.
- [ ] Final live-market workflow test — must still be validated during an actual market session; paper-only code checks cannot prove live-data behavior.

## 10. Final paper-trading flow

`09:15 market open`
→ `Today's Open + PDH + PDL`
→ `NIFTY 500 >= +0.25% → activate BUY / NIFTY 500 <= -0.25% → activate SELL`
→ `build BUY/SELL waiting list`
→ `completed 1-minute Close checks every 30 seconds`
→ `BUY: Close below PDH → wait for Close back to Today's Open`
→ `SELL: Close above PDL → wait for Close back to Today's Open`
→ `QUALIFIED`
→ `ATR% → RVOL → Beta → traded value ranking`
→ `final NIFTY + stock-price confirmation`
→ `current market price`
→ `quantity from ₹1,400–₹1,500 risk`
→ `BUY SL=PDH / SELL SL=PDL`
→ `1.25R target`
→ `immediate paper entry`
→ `14:00 no new entries`
→ `15:00 square-off`
→ `journal + CSV/master data + analysis + downloads`
