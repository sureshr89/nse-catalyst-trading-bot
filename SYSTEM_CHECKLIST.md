# NIFTY 500 Trading Bot — Current System Checklist

Last reviewed: 2026-08-21

## 1. Runtime
- [x] One canonical `MasterEngine` in `engine/master_engine.py`.
- [x] `main.py` is the compatibility/production entrypoint.
- [x] `engine/cycle_runner.py` is the only strategy/execution cycle.
- [x] Streamlit worker runs paper trading through the canonical engine.
- [x] Entry window: 09:45–14:00 IST.
- [x] Mandatory paper square-off: 15:00 IST.
- [x] `LIVE_TRADING=False`; paper trading only.

## 2. Live NIFTY 500 data
- [x] Universe: exactly 500 NIFTY 500 constituents.
- [x] Security mapping: Dhan NSE_EQ.
- [x] Live collection window: 15 seconds.
- [x] Dhan market-feed OHLC fetch uses one request for all 500 instruments.
- [x] Dhan supports up to 1,000 instruments per market-quote request; the old 100-stock burst was removed.
- [x] 98% trade-readiness gate = 490/500.
- [x] Valid live prices are shared by breadth, sectors, dashboard and S1–S5.
- [x] A failed/429 quote response does not overwrite the last good bridge cache.

## 3. Market alignment
- [x] NIFTY 500 live change.
- [x] Advances / declines / unchanged.
- [x] A/D ratio.
- [x] Positive / negative sectors.
- [x] Sector mapping is cached instead of being rebuilt every 15 seconds.
- [x] BUY: NIFTY 500 > 0%, A/D > 1, positive sectors > negative sectors.
- [x] SELL: NIFTY 500 < 0%, A/D < 1, negative sectors > positive sectors.
- [x] Market alignment is a hard trade gate.

## 4. References
- [x] PDH / PDL / previous close are Dhan-derived.
- [x] Full-universe daily reference preparation is paced at Dhan's documented data rate.
- [x] References are cached for the trading session.
- [x] Stocks without valid references are skipped; they do not invalidate otherwise valid stocks.

## 5. S1–S5
- [x] S1 — PDH/PDL sweep + open reclaim.
- [x] S2 — PDH/PDL breakout + retest.
- [x] S3 — opposite PDH/PDL sweep + open reversal.
- [x] S4 — completed intraday high/low breakout.
- [x] S5 — direct PDH/PDL breakout.
- [x] S1/S3/S5 do not require a previous candle merely for diagnostics.
- [x] S2/S4 require completed intraday data because their setup definitions depend on it.
- [x] S1/S3/S5 are evaluated before any historical 1-minute request.
- [x] S2/S4 historical requests are only made when needed.
- [x] Live LTP is used for the actual entry.

## 6. Risk / paper execution
- [x] ₹2,50,000 capital allocation per trade.
- [x] ₹1,400–₹1,500 intended actual risk.
- [x] 1.25R target.
- [x] Maximum 1 trade per strategy per day.
- [x] Daily strategy loss limit ₹1,500.
- [x] Paper execution only.
- [x] Mandatory 15:00 square-off.

## 7. Dashboard
- [x] Compact market-alignment cards.
- [x] Live coverage and 98% gate cards.
- [x] S1–S5 strategy cards with readable trade details.
- [x] Sector performance table removed from the UI.
- [x] Raw 500-stock table removed from the production UI.
- [x] One Master CSV download.
- [x] One Daily Trading Tip at the bottom.
- [x] No production TEST tab.
- [x] Auto refresh: 15 seconds.

## 8. Cleanup
- [x] Obsolete tabbed/test dashboard wrapper removed.
- [x] Obsolete standalone NIFTY 500 diagnostic module removed.
- [x] Obsolete duplicate `data/price_data.py` removed; `market/price_data.py` is canonical.
- [x] `main.py` no longer opens the old test-tab wrapper.

## 9. Verification still required
- [ ] Run the current full regression workflow on `main` after these changes.
- [ ] Observe one live market session with coverage >=490/500.
- [ ] Confirm a qualifying paper setup creates a trade record.

The final live observation is the only part that code review/tests cannot prove by themselves.
