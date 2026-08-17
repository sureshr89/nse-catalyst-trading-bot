"""Risk gate isolated to Strategy 2 journal/state.

Strategy 2 must never inherit Strategy 1's per-stock trade counts, realized P&L,
or open-risk state. The validation rules remain the same as the main risk gate.
"""
from pathlib import Path
import json

from strategy.risk_engine import RiskEngine


class Strategy2RiskEngine(RiskEngine):
    """RiskEngine using only Strategy 2 persistence and its own ₹2.5 lakh pool."""

    STRATEGY2_CAPITAL = 250000.0
    STRATEGY2_TRADES = Path("outputs/strategy2_trades.csv")
    STRATEGY2_STATE = Path("outputs/strategy2_paper_engine_state.json")

    def __init__(self):
        super().__init__()
        self.total_capital = self.STRATEGY2_CAPITAL
        self.restore_today_trade_counts()

    def restore_today_trade_counts(self):
        """Restore only Strategy 2 trades for today's per-stock limit."""
        self.trade_counts = {}
        path = self.STRATEGY2_TRADES
        if not path.exists():
            return
        try:
            import pandas as pd
            df = pd.read_csv(path)
        except Exception:
            return
        if df.empty or "symbol" not in df.columns or "entry_time" not in df.columns:
            return
        today = self._today_ist()
        seen = set()
        for row in df.itertuples(index=False):
            try:
                if self._entry_date_ist(getattr(row, "entry_time", "")) != today:
                    continue
                status = str(getattr(row, "status", "")).strip().upper()
                if status.startswith("MISSED_CAPITAL"):
                    continue
                symbol = str(getattr(row, "symbol", "")).strip().upper()
                if not symbol:
                    continue
                trade_id = str(getattr(row, "trade_id", "")).strip()
                key = (symbol, trade_id) if trade_id else (
                    symbol,
                    str(getattr(row, "signal", "")).strip().upper(),
                    str(getattr(row, "entry_time", "")).strip(),
                    str(getattr(row, "entry", "")).strip(),
                )
                if key in seen:
                    continue
                seen.add(key)
                self.trade_counts[symbol] = self.trade_counts.get(symbol, 0) + 1
            except Exception:
                continue

    def _current_daily_risk_state(self):
        """Calculate realized P&L and open risk using Strategy 2 files only."""
        realized_pnl = 0.0
        path = self.STRATEGY2_TRADES
        if path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(path)
                if not df.empty and {"status", "exit_time", "pnl"}.issubset(df.columns):
                    closed = df[df["status"].astype(str).str.upper().eq("CLOSED")].copy()
                    if not closed.empty:
                        dates = closed["exit_time"].map(self._entry_date_ist)
                        pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
                        realized_pnl = float(pnl[dates.eq(self._today_ist())].sum())
            except Exception:
                realized_pnl = 0.0

        open_risk = 0.0
        if self.STRATEGY2_STATE.exists():
            try:
                state = json.loads(self.STRATEGY2_STATE.read_text(encoding="utf-8"))
                positions = state.get("open_positions", {}) if isinstance(state, dict) else {}
                if isinstance(positions, dict):
                    for position in positions.values():
                        if not isinstance(position, dict):
                            continue
                        entry = self._number(position.get("entry"))
                        stop = self._number(position.get("stop_loss"))
                        quantity = self._number(position.get("quantity"))
                        if entry is not None and stop is not None and quantity is not None and quantity > 0:
                            open_risk += abs(entry - stop) * quantity
            except Exception:
                open_risk = 0.0
        return round(realized_pnl, 2), round(open_risk, 2)
