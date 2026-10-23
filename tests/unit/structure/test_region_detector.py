"""Unit tests for RegionDetector (metadata blocks and table boundaries)."""

from pathlib import Path

import pytest

from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.region_detector import RegionDetector


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_detect_metadata_and_table_regions(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_scattered" / "scattered_with_metadata.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-scattered",
        project_id="proj-scattered",
        max_preview_rows=30,
    )

    sheet = structure.sheets[0]
    grid = OccupancyGrid(
        max_row=sheet.max_row,
        max_col=sheet.max_col,
        cells=sheet.cells_sample,
        merged_ranges=sheet.merged_ranges,
    )

    detector = RegionDetector(grid)
    boundaries, metadata_entries = detector.detect_regions()

    # scattered_with_metadata.xlsx has metadata block (rows 1-3) and table (rows 6-26)
    assert len(boundaries) == 2

    meta_boundary = next(b for b in boundaries if b.region_type == "metadata_block")
    table_boundary = next(b for b in boundaries if b.region_type == "table")

    assert meta_boundary.min_row == 1
    assert meta_boundary.max_row == 3

    assert table_boundary.min_row == 6
    assert table_boundary.max_row == 26
    assert table_boundary.min_col == 1
    assert table_boundary.max_col == 3

    # Check extracted metadata
    keys = {m.key: m.value for m in metadata_entries}
    assert "Facility" in keys
    assert keys["Facility"] == "Compressor Station 4"
    assert "Operator" in keys
    assert keys["Operator"] == "AICONNEX Client"
    assert "Report Date" in keys
    assert keys["Report Date"] == "2026-03-01"


def test_identify_header_band(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-complex",
        project_id="proj-complex",
        max_preview_rows=25,
    )

    sheet = structure.sheets[0]
    grid = OccupancyGrid(
        max_row=sheet.max_row,
        max_col=sheet.max_col,
        cells=sheet.cells_sample,
        merged_ranges=sheet.merged_ranges,
    )

    detector = RegionDetector(grid)
    boundaries, _ = detector.detect_regions()
    table_boundary = boundaries[0]

    header_rows, data_start_row = detector.identify_header_band(table_boundary)

    # In merged_equipment_headers, rows 1, 2, 3 are text headers; data begins at row 4
    assert header_rows == [1, 2, 3]
    assert data_start_row == 4
