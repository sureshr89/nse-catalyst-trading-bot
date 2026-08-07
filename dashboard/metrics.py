"""
Dashboard Metrics

Calculates trading statistics for the Streamlit dashboard.
"""

import pandas as pd


TOTAL_CAPITAL = 250000


def calculate_metrics(trades: pd.DataFrame):

    if trades.empty:

        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "average_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "current_equity": TOTAL_CAPITAL,
            "available_capital": TOTAL_CAPITAL,
            "used_capital": 0.0,
            "open_positions": 0,
            "closed_positions": 0,
            "max_drawdown": 0.0,
        }

    trades = trades.copy()

    trades["pnl"] = pd.to_numeric(
        trades["pnl"],
        errors="coerce"
    ).fillna(0)

    total_trades = len(trades)

    winning = len(
        trades[
            trades["pnl"] > 0
        ]
    )

    losing = len(
        trades[
            trades["pnl"] < 0
        ]
    )

    breakeven = len(
        trades[
            trades["pnl"] == 0
        ]
    )

    total_pnl = float(
        trades["pnl"].sum()
    )

    average_pnl = float(
        trades["pnl"].mean()
    )

    gross_profit = float(
        trades.loc[
            trades["pnl"] > 0,
            "pnl"
        ].sum()
    )

    gross_loss = abs(
        float(
            trades.loc[
                trades["pnl"] < 0,
                "pnl"
            ].sum()
        )
    )

    if gross_loss == 0:
        profit_factor = 0.0
    else:
        profit_factor = gross_profit / gross_loss

    if "status" in trades.columns:

        open_positions = len(
            trades[
                trades["status"] == "OPEN"
            ]
        )

        closed_positions = len(
            trades[
                trades["status"] == "CLOSED"
            ]
        )

    else:

        open_positions = 0
        closed_positions = total_trades

    if total_trades > 0:

        win_rate = (
            winning /
            total_trades
        ) * 100

    else:

        win_rate = 0

    current_equity = (
        TOTAL_CAPITAL +
        total_pnl
    )

    if "position_value" in trades.columns:

        used_capital = float(
            trades.loc[
                trades["status"] == "OPEN",
                "position_value"
            ].sum()
        )

    else:

        used_capital = 0.0

    available_capital = (
        current_equity -
        used_capital
    )

    equity = (
        TOTAL_CAPITAL +
        trades["pnl"].cumsum()
    )

    running_max = equity.cummax()

    drawdown = (
        running_max -
        equity
    )

    max_drawdown = float(
        drawdown.max()
    )

    return {

        "total_trades": total_trades,

        "winning_trades": winning,

        "losing_trades": losing,

        "breakeven_trades": breakeven,

        "win_rate": round(
            win_rate,
            2
        ),

        "total_pnl": round(
            total_pnl,
            2
        ),

        "average_pnl": round(
            average_pnl,
            2
        ),

        "gross_profit": round(
            gross_profit,
            2
        ),

        "gross_loss": round(
            gross_loss,
            2
        ),

        "profit_factor": round(
            profit_factor,
            2
        ),

        "current_equity": round(
            current_equity,
            2
        ),

        "available_capital": round(
            available_capital,
            2
        ),

        "used_capital": round(
            used_capital,
            2
        ),

        "open_positions": open_positions,

        "closed_positions": closed_positions,

        "max_drawdown": round(
            max_drawdown,
            2
        ),
    }