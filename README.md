# NSE Catalyst Trading Bot

## Clean active system — Dhan-only NIFTY 500 S1-S5

NSE Catalyst is a **paper-trading-only** NIFTY 500 scanner. The active runtime has one market-data source (**Dhan**) and one strategy engine containing exactly five strategies: S1-S5.

### Authoritative data flow

Dhan instrument master → verified NIFTY 500 mapping → fresh Dhan NIFTY 500 market quotes → A/D + sector counts + NIFTY 500 alignment → candidate prefilter → Dhan completed 1-minute candles for candidates → S1-S5 → risk → paper trade → journal/dashboard.

**Yahoo Finance is not used.** No Yahoo price, Yahoo fallback, Yahoo news or legacy strategy path may create a signal.

### Common market gate

The active production gate requires **at least 490 verified fresh NIFTY 500 quotes out of the 500-stock universe**. It does not require an impossible 500/500 response when a small number of valid symbols are unavailable from the provider.

BUY requires:
- NIFTY 500 change > 0%
- A/D ratio > 1
- positive sector count > negative sector count
- at least 490/500 verified fresh market quotes

SELL requires the inverse:
- NIFTY 500 change < 0%
- A/D ratio < 1
- negative sector count > positive sector count
- at least 490/500 verified fresh market quotes

### S1 — PDH/PDL Sweep + Open Reclaim

BUY: Today's Open > PDH → today's Low touches/sweeps PDH → live Dhan LTP > Today's Open → BUY.

SELL: Today's Open < PDL → today's High touches/sweeps PDL → live Dhan LTP < Today's Open → SELL.

SL = PDH for BUY / PDL for SELL.

### S2 — PDH/PDL Breakout + Retest

BUY: completed 1-minute history breaks PDH → pullback reaches PDH → live Dhan LTP ≥ PDH → BUY.

SELL: completed 1-minute history breaks PDL → pullback reaches PDL → live Dhan LTP ≤ PDL → SELL.

SL = pullback Low for BUY / pullback High for SELL.

### S3 — Opposite PDH/PDL Sweep + Open Reversal

BUY: Today's Open is inside PDH/PDL → today's Low touches/sweeps PDL → live Dhan LTP > Today's Open → BUY.

SELL: Today's Open is inside PDH/PDL → today's High touches/sweeps PDH → live Dhan LTP < Today's Open → SELL.

SL = Today's Low for BUY / Today's High for SELL.

### S4 — Intraday High/Low Breakout

BUY: live Dhan LTP breaks the previously completed intraday High.

SELL: live Dhan LTP breaks the previously completed intraday Low.

SL = previous intraday Low for BUY / previous intraday High for SELL.

### S5 — Direct PDH/PDL Breakout

BUY: live Dhan LTP > PDH.

SELL: live Dhan LTP < PDL.

SL = PDH for BUY / PDL for SELL.

### Risk and execution

- Paper trading only; live order placement is disabled.
- Capital allocation: ₹2,50,000 per trade.
- Required actual risk: ₹1,400–₹1,500.
- Target: 1.25R.
- Entry window: 09:45–14:00 IST.
- Mandatory paper square-off: 15:00 IST.
- Strategy-level trade/loss limits are controlled centrally by configuration and the risk engine.

### Clean architecture

- `engine/master_engine.py` — single runtime decision path
- `market/dhan_data.py` — Dhan authentication, instrument mapping, quotes and historical candles
- `market/price_data.py` — Dhan-only candle/live-price adapter
- `data/reference_store.py` — PDH/PDL/PDC references
- `strategy/nifty500_price_action_strategies.py` — pure S1-S5 signal contract
- `strategy/contracts.py` — authoritative S1-S5 documentation contract
- `strategy/risk_engine.py` — final risk gate
- `papertrade/` — paper execution and journal
- `dashboard/` — presentation only

Legacy open-reversal, gap-extension, Yahoo and monkey-patch strategy layers have been removed from the active runtime.

### Testing

GitHub Actions compiles the repository and runs pytest on every push and pull request. Tests are being migrated to the clean S1-S5 contract; no legacy strategy test should be required for the active runtime.

**Real-money trading must remain disabled until the complete paper-trading path and CI suite are verified.**
