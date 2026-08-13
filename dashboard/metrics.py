"""Dashboard metrics for the paper-trading journal."""

import pandas as pd

TOTAL_CAPITAL = 250000


def calculate_metrics(trades: pd.DataFrame):
    if trades is None or trades.empty:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "breakeven_trades": 0, "win_rate": 0.0, "total_pnl": 0.0,
            "average_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
            "profit_factor": 0.0, "current_equity": TOTAL_CAPITAL,
            "available_capital": TOTAL_CAPITAL, "used_capital": 0.0,
            "open_positions": 0, "closed_positions": 0, "max_drawdown": 0.0,
        }

    frame = trades.copy()
    if "status" in frame.columns:
        status = frame["status"].astype(str).str.upper()
        open_frame = frame[status == "OPEN"].copy()
        closed = frame[status == "CLOSED"].copy()
    else:
        open_frame = pd.DataFrame(columns=frame.columns)
        closed = frame.copy()

    if "pnl" not in closed.columns:
        closed["pnl"] = 0.0
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)

    total_trades = len(closed)
    winning = int((closed["pnl"] > 0).sum())
    losing = int((closed["pnl"] < 0).sum())
    breakeven = int((closed["pnl"] == 0).sum())
    total_pnl = float(closed["pnl"].sum())
    average_pnl = float(closed["pnl"].mean()) if total_trades else 0.0
    gross_profit = float(closed.loc[closed["pnl"] > 0, "pnl"].sum())
    gross_loss = abs(float(closed.loc[closed["pnl"] < 0, "pnl"].sum()))
    profit_factor = gross_profit / gross_loss if gross_loss else 0.0

    if "position_value" in open_frame.columns:
        used_capital = float(pd.to_numeric(open_frame["position_value"], errors="coerce").fillna(0).sum())
    else:
        used_capital = 0.0

    current_equity = TOTAL_CAPITAL + total_pnl
    available_capital = current_equity - used_capital

    if total_trades:
        equity = TOTAL_CAPITAL + closed["pnl"].cumsum()
        running_max = equity.cummax()
        max_drawdown = float((running_max - equity).max())
    else:
        max_drawdown = 0.0

    return {
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": losing,
        "breakeven_trades": breakeven,
        "win_rate": round(winning / total_trades * 100, 2) if total_trades else 0.0,
        "total_pnl": round(total_pnl, 2),
        "average_pnl": round(average_pnl, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "current_equity": round(current_equity, 2),
        "available_capital": round(available_capital, 2),
        "used_capital": round(used_capital, 2),
        "open_positions": len(open_frame),
        "closed_positions": total_trades,
        "max_drawdown": round(max_drawdown, 2),
    }
