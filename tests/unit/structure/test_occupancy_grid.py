"""Unit tests for OccupancyGrid and type signature matrix."""

from src.compiler.contracts.structure import CellDetail
from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.types import CellTypeSignature


def test_occupancy_grid_type_classification() -> None:
    cells = [
        CellDetail(coordinate="A1", row=1, column=1, data_type="s", raw_value="HEADER_A"),
        CellDetail(coordinate="B1", row=1, column=2, data_type="s", raw_value="HEADER_B"),
        CellDetail(coordinate="A2", row=2, column=1, data_type="d", raw_value="2026-01-01"),
        CellDetail(coordinate="B2", row=2, column=2, data_type="n", raw_value=42.5),
        CellDetail(coordinate="C2", row=2, column=3, data_type="duration", raw_value=3600.0),
    ]

    grid = OccupancyGrid(max_row=2, max_col=3, cells=cells)

    assert grid.get_signature(1, 1) == CellTypeSignature.TEXT
    assert grid.get_signature(1, 2) == CellTypeSignature.TEXT
    assert grid.get_signature(1, 3) == CellTypeSignature.EMPTY
    assert grid.get_signature(2, 1) == CellTypeSignature.DATETIME
    assert grid.get_signature(2, 2) == CellTypeSignature.NUMERIC
    assert grid.get_signature(2, 3) == CellTypeSignature.DURATION


def test_occupancy_grid_ratios_and_densities() -> None:
    cells = [
        CellDetail(coordinate="A1", row=1, column=1, data_type="s", raw_value="TITLE"),
        CellDetail(coordinate="B1", row=1, column=2, data_type="s", raw_value="COL"),
        CellDetail(coordinate="A2", row=2, column=1, data_type="n", raw_value=10),
        CellDetail(coordinate="B2", row=2, column=2, data_type="n", raw_value=20),
    ]

    grid = OccupancyGrid(max_row=3, max_col=2, cells=cells)

    # Row 1 text ratio = 1.0, data ratio = 0.0
    assert grid.row_non_empty_count(1) == 2
    assert grid.row_text_ratio(1) == 1.0
    assert grid.row_data_ratio(1) == 0.0

    # Row 2 text ratio = 0.0, data ratio = 1.0
    assert grid.row_non_empty_count(2) == 2
    assert grid.row_text_ratio(2) == 0.0
    assert grid.row_data_ratio(2) == 1.0

    # Row 3 is completely blank
    assert grid.row_non_empty_count(3) == 0
    assert grid.find_blank_rows(1, 3) == [3]
