# NSE Catalyst Trading Bot

## Overview

A Python-based paper trading bot for the NIFTY LargeMidcap 250 universe.

The bot automatically:

- Scans NIFTY LargeMidcap 250 stocks
- Determines overall NIFTY market direction
- Analyzes industry strength
- Identifies stock direction
- Detects 5-minute pullback setups
- Confirms entries using 1-minute breakout candles
- Applies risk management
- Executes paper trades
- Maintains a trade journal

---

## Trading Strategy

### Buy Conditions

- NIFTY must be Bullish
- Industry must be Bullish
- Stock must be Bullish
- Valid 5-minute pullback
- Completed 1-minute candle closes above breakout level
- Entry only after 09:45 AM

### Sell Conditions

- NIFTY must be Bearish
- Industry must be Bearish
- Stock must be Bearish
- Valid 5-minute pullback
- Completed 1-minute candle closes below breakdown level
- Entry only after 09:45 AM

---

## Risk Management

- Capital: ₹2,50,000
- Risk per Trade: ₹1,250 (0.5%)
- Risk Reward: 1:1
- Maximum 1 trade per stock per day
- Mandatory Square Off: 3:00 PM

---

## Current Features

- ✅ Stock Universe Engine