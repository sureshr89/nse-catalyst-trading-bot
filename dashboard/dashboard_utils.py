"""Shared dashboard data-export helpers."""

from __future__ import annotations

import io

import pandas as pd
from openpyxl import Workbook


def _tag_frame(frame: pd.DataFrame | None, record_type: str) -> pd.DataFrame:
    """Return a copy of a frame with the dashboard record type attached."""
    if frame is None:
        frame = pd.DataFrame()
    result = frame.copy()
    result.insert(0, "Record Type", record_type)
    return result


def build_single_sheet_master_excel(
    trades: pd.DataFrame | None,
    signals: pd.DataFrame | None,
    gaps: pd.DataFrame | None,
) -> bytes:
    """Build the cumulative dashboard export as one ``ALL DATA`` sheet.

    The three source tables are kept as rows in a single workbook.  Columns
    are the union of all source columns, while ``Record Type`` identifies
    whether each row came from the trade journal, signal journal, or gap board.
    """
    frames = [
        _tag_frame(trades, "TRADE"),
        _tag_frame(signals, "SIGNAL"),
        _tag_frame(gaps, "GAP_BOARD"),
    ]

    columns: list[str] = []
    for frame in frames:
        for column in frame.columns:
            if column not in columns:
                columns.append(column)

    combined = pd.concat(
        [frame.reindex(columns=columns) for frame in frames],
        ignore_index=True,
    )

    output = io.BytesIO()
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ALL DATA"

    worksheet.append(columns)
    for row in combined.itertuples(index=False, name=None):
        worksheet.append(list(row))

    workbook.save(output)
    return output.getvalue()
