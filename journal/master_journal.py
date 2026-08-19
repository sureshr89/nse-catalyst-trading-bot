"""Build one consolidated paper-trading journal CSV for S1-S5.
The final row is a daily quote so the exported master sheet always ends with a quote.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "strategy_journal_master.csv"
IST = ZoneInfo("Asia/Kolkata")
QUOTES = [
    "Process first. Profit follows disciplined execution.",
    "Protect capital, wait for alignment, then act.",
    "A good trade is a rule-following trade, not just a winning trade.",
    "Consistency comes from repeating a tested process.",
    "No setup is also a valid decision.",
    "Risk is fixed before the entry; everything else follows.",
    "Trade the setup, not the emotion around it.",
]

COLUMNS = [
    "row_type", "date", "strategy", "symbol", "side", "entry_time", "exit_time",
    "entry", "exit", "stop_loss", "target", "quantity", "actual_risk", "pnl",
    "exit_reason", "nifty500_pct", "sector_pct", "ad_ratio", "ad_coverage",
    "previous_candle", "pdh", "pdl", "today_open", "today_high", "today_low",
    "notes",
]


def _quote(day):
    return QUOTES[day.toordinal() % len(QUOTES)]


def build_journal(trades_path=None, output_path=None):
    trades_path = Path(trades_path or ROOT / "outputs" / "trades.csv")
    output_path = Path(output_path or OUT)
    rows = []
    if trades_path.exists():
        try:
            df = pd.read_csv(trades_path)
            for _, r in df.iterrows():
                strategy = str(r.get("strategy", "")).upper()
                if strategy in {"STRATEGY_1", "OPEN_RETURN"}: strategy = "S1"
                elif strategy.startswith("STRATEGY_"): strategy = "S" + strategy.split("_")[-1]
                rows.append({c: r.get(c, "") for c in COLUMNS if c in r.index})
                rows[-1]["row_type"] = "TRADE"
                rows[-1]["strategy"] = strategy
        except Exception:
            pass
    day = datetime.now(IST).date()
    rows.append({
        "row_type": "DAILY_QUOTE", "date": day.isoformat(), "strategy": "ALL",
        "notes": _quote(day),
    })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})
    return output_path


if __name__ == "__main__":
    print(build_journal())
