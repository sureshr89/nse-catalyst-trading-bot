# NIFTY 500 Trading Bot — Code & System Checklist

Last reviewed: 2026-08-18

## 1. Runtime / worker
- [x] `bot_runner.py` owns the single persistent paper worker for both strategies.
- [x] Weekday loop, 09:45 entry start, 14:00 last entry, 15:00 mandatory square-off.
- [x] Live trading hard-blocked by `LIVE_TRADING=False` and paper-trading checks.
- [x] Master data refresh runs after final square-off.
- [x] Control scan interval is configured in `config/settings.py` (`5` seconds currently).
- [x] Dashboard UI refresh is 5 seconds.

## 2. Market data / universe
- [x] NIFTY 500 universe is used for Strategy 1 and Strategy 2 candidate discovery.
- [x] Reference data provides previous close, PDH and PDL.
- [x] Market data is normalized to IST and forming 1-minute data is excluded where completed data is required.
- [x] NIFTY 500 market filter uses the latest available index change supplied by `PriceData`.
- [x] Scanner minimum synchronized 1-minute stock coverage is currently `60%` (`MIN_MARKET_DATA_COVERAGE`).

## 3. Strategy 1 — PDH/PDL + Open Return
- [x] BUY market gate: NIFTY 500 `>= +0.25%`.
- [x] SELL market gate: NIFTY 500 `<= -0.25%`.
- [x] BUY candidate: `Today's Open > PDH`.
- [x] SELL candidate: `Today's Open < PDL`.
- [x] BUY live sequence: price must first fall to/touch PDH, then live LTP must return to/above Today's Open.
- [x] SELL live sequence: price must first rise to/touch PDL, then live LTP must return to/below Today's Open.
- [x] No candle-close confirmation is used for the active trigger.
- [x] Final entry uses the current live market price and re-checks the market/price conditions.
- [x] BUY SL = PDH.
- [x] SELL SL = PDL.
- [x] Target = 1.25R from actual live entry-to-SL distance.
- [x] Entry window is `09:45–14:00 IST`.

## 4. Strategy 2 — Gap Extension Reversal
- [x] SELL candidate: `Today's Open > PDH`, price extends above Open, then live LTP crosses below Open.
- [x] BUY candidate: `Today's Open < PDL`, price extends below Open, then live LTP crosses above Open.
- [x] Strong opposite NIFTY 500 movement blocks the setup; this is a soft protective filter.
- [x] Entry is live LTP; no candle-close entry confirmation.
- [x] SELL SL = trigger-day high.
- [x] BUY SL = trigger-day low.
- [x] SELL target = PDH; BUY target = PDL, subject to minimum 1.25R.
- [x] Strategy 2 has isolated paper capital/state/journal files.

## 5. Scanner / state management
- [x] Strategy 1 waiting/qualified states persist across scanner cycles.
- [x] Candidate identity prevents repeated finalization of the same setup.
- [x] Qualified candidates are ranked before final execution.
- [x] Final entry re-checks current NIFTY 500 alignment and stock price relative to Open.
- [x] Diagnostics record coverage, waiting counts, qualified counts, ranking and final signals.
- [x] Strategy contract version is centralized in `strategy/contracts.py` and currently `2026.08.18.v3`.

## 6. Risk / execution
- [x] Maximum risk per trade = ₹1,500.
- [x] Intended actual risk = ₹1,400–₹1,500.
- [x] Minimum R:R = 1:1.25.
- [x] Maximum 1 trade per stock per day.
- [x] Strategy 1 maximum open positions = 2.
- [x] Strategy 2 maximum open positions = 2.
- [x] Daily loss/profit limits are enforced by the respective runtime/risk engine.
- [x] Paper execution validates risk before opening.
- [x] Fast position monitoring checks live price independently of the scanner.
- [x] 15:00 square-off is mandatory.

## 7. Dashboard / UI alignment
- [x] `dashboard/pages/current_trading.py` is the active Strategy 1 page.
- [x] `dashboard/pages/strategy2_current.py` is the active Strategy 2 page.
- [x] Both pages use `strategy_metadata()` as the authoritative strategy identity/version source.
- [x] Both pages display live-LTP entry/SL/target behavior.
- [x] Strategy 2 status is derived from the single `bot_runner.py` worker; the old standalone Strategy 2 worker is not used.
- [x] Unified trade/signal downloads combine Strategy 1 + Strategy 2 records and include a `strategy` column.

## 8. Persistence / outputs
- [x] Strategy 1 uses `outputs/trades.csv`, `outputs/signals.csv`, `outputs/paper_engine_state.json` and `outputs/waiting_candidates.json`.
- [x] Strategy 2 uses `outputs/strategy2_trades.csv`, `outputs/strategy2_signals.csv`, `outputs/strategy2_paper_engine_state.json` and `outputs/strategy2_diagnostics.json`.
- [x] The dashboard's trade/signal download layer presents unified S1+S2 CSVs rather than separate strategy CSV downloads.
- [x] Gap boards and strategy-specific JSON diagnostics remain separate because their schemas/meaning are strategy-specific.

## 9. Automated checks
- [x] GitHub Actions compiles every Python file.
- [x] Core import checks run after compilation succeeds.
- [x] Strategy 1 and Strategy 2 contract/integration tests exist.
- [x] Strategy 2 risk-adjustment tests exist.
- [x] Regression tests now verify that Strategy 1 cannot qualify without a genuine PDH/PDL touch sequence.
- [ ] Final live-market workflow test — code/tests cannot prove live-data behavior until observed during an actual market session.

## 10. Final paper-trading flow

`09:15 market open`
→ `NIFTY 500 + Today's Open + PDH + PDL`
→ `09:45 entry window starts`
→ `S1: NIFTY 500 gate + Open > PDH / Open < PDL`
→ `S1: live LTP touches PDH/PDL in the required direction`
→ `S1: live LTP returns through Today's Open`
→ `S2: gap extension beyond Open`
→ `S2: live LTP reverses through Open`
→ `final market/risk checks`
→ `live paper entry`
→ `live SL/target monitoring`
→ `14:00 no new entries`
→ `15:00 square-off`
→ `journal + master data + analysis + unified downloads`
