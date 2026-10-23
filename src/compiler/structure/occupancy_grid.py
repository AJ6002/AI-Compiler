"""Occupancy and type grid representation for spreadsheet layout recognition."""

from __future__ import annotations

from typing import Any

from src.compiler.contracts.structure import CellDetail
from src.compiler.structure.types import CellTypeSignature


class OccupancyGrid:
    """2D matrix tracking cell types, values, and merged ranges across a worksheet."""

    def __init__(
        self,
        max_row: int,
        max_col: int,
        cells: list[CellDetail],
        merged_ranges: list[str] | None = None,
    ) -> None:
        self.max_row = max_row
        self.max_col = max_col
        self.merged_ranges = merged_ranges or []

        # Internal cell map: (row, col) -> (signature, raw_value, is_merged)
        self._grid: dict[tuple[int, int], tuple[CellTypeSignature, Any, bool]] = {}

        for cell in cells:
            sig = self._classify_type(cell.data_type, cell.raw_value)
            self._grid[(cell.row, cell.column)] = (sig, cell.raw_value, cell.is_merged)

    @staticmethod
    def _classify_type(data_type: str, raw_value: Any) -> CellTypeSignature:
        """Map contract data_type and value to CellTypeSignature."""
        if raw_value is None or raw_value == "":
            return CellTypeSignature.EMPTY
        if data_type == "s":
            return CellTypeSignature.TEXT
        if data_type == "n":
            return CellTypeSignature.NUMERIC
        if data_type in ("d", "datetime"):
            return CellTypeSignature.DATETIME
        if data_type == "duration":
            return CellTypeSignature.DURATION
        if data_type == "f":
            return CellTypeSignature.FORMULA
        if data_type == "b":
            return CellTypeSignature.BOOLEAN
        if data_type == "e":
            return CellTypeSignature.ERROR
        # Fallback check on Python type
        if isinstance(raw_value, (int, float)):
            return CellTypeSignature.NUMERIC
        if isinstance(raw_value, str):
            return CellTypeSignature.TEXT
        return CellTypeSignature.EMPTY

    def get_cell(self, row: int, col: int) -> tuple[CellTypeSignature, Any, bool]:
        """Return (signature, raw_value, is_merged) for given cell coordinate."""
        return self._grid.get((row, col), (CellTypeSignature.EMPTY, None, False))

    def get_value(self, row: int, col: int) -> Any:
        """Return raw value of cell."""
        return self._grid.get((row, col), (CellTypeSignature.EMPTY, None, False))[1]

    def get_signature(self, row: int, col: int) -> CellTypeSignature:
        """Return type signature of cell."""
        return self._grid.get((row, col), (CellTypeSignature.EMPTY, None, False))[0]

    def row_non_empty_count(self, row: int, min_col: int = 1, max_col: int | None = None) -> int:
        """Count non-empty cells in the given row span."""
        end_col = max_col or self.max_col
        count = 0
        for c in range(min_col, end_col + 1):
            if self.get_signature(row, c) != CellTypeSignature.EMPTY:
                count += 1
        return count

    def row_text_ratio(self, row: int, min_col: int = 1, max_col: int | None = None) -> float:
        """Ratio of text cells among non-empty cells in the row span."""
        end_col = max_col or self.max_col
        non_empty = 0
        text_count = 0
        for c in range(min_col, end_col + 1):
            sig = self.get_signature(row, c)
            if sig != CellTypeSignature.EMPTY:
                non_empty += 1
                if sig == CellTypeSignature.TEXT:
                    text_count += 1
        return (text_count / non_empty) if non_empty > 0 else 0.0

    def row_data_ratio(self, row: int, min_col: int = 1, max_col: int | None = None) -> float:
        """Ratio of data cells (numeric, date, duration, formula) among non-empty cells."""
        end_col = max_col or self.max_col
        non_empty = 0
        data_count = 0
        for c in range(min_col, end_col + 1):
            sig = self.get_signature(row, c)
            if sig != CellTypeSignature.EMPTY:
                non_empty += 1
                if sig in (
                    CellTypeSignature.NUMERIC,
                    CellTypeSignature.DATETIME,
                    CellTypeSignature.DURATION,
                    CellTypeSignature.FORMULA,
                ):
                    data_count += 1
        return (data_count / non_empty) if non_empty > 0 else 0.0

    def find_blank_rows(self, min_row: int, max_row: int) -> list[int]:
        """Return list of completely empty row indices within the specified range."""
        blank_rows: list[int] = []
        for r in range(min_row, max_row + 1):
            if self.row_non_empty_count(r) == 0:
                blank_rows.append(r)
        return blank_rows
