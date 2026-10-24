"""Unit tests and benchmarks for CalamineReader verifying parity and speed."""

import time
from pathlib import Path

import openpyxl
import pytest

from src.compiler.readers.calamine_reader import CalamineReader
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_calamine_vs_openpyxl_parity(fixtures_dir: Path) -> None:
    """Verify CalamineReader emits identical coordinates, raw_values, and data_types."""
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    sheet_name = "SimpleReadings"

    calamine_reader = CalamineReader()
    openpyxl_reader = OpenpyxlReader()

    c_cells = {
        c.coordinate: c
        for batch in calamine_reader.extract_sheet_cells(xlsx_path, sheet_name)
        for c in batch
    }
    o_cells = {
        c.coordinate: c
        for batch in openpyxl_reader.extract_sheet_cells(xlsx_path, sheet_name)
        for c in batch
    }

    assert len(c_cells) == len(o_cells)
    assert len(c_cells) == 459

    for coord, c_cell in c_cells.items():
        assert coord in o_cells, f"Coordinate {coord} missing from OpenpyxlReader output"
        o_cell = o_cells[coord]
        assert (
            c_cell.raw_value == o_cell.raw_value
        ), f"Raw value mismatch at {coord}: {c_cell.raw_value} != {o_cell.raw_value}"
        assert (
            c_cell.data_type == o_cell.data_type
        ), f"Data type mismatch at {coord}: {c_cell.data_type} != {o_cell.data_type}"
        assert c_cell.row == o_cell.row
        assert c_cell.column == o_cell.column


def test_calamine_speed_advantage(tmp_path: Path) -> None:
    """Assert Calamine is significantly faster than Openpyxl on a 10,000-row sheet (ratio < 0.5)."""
    bench_file = tmp_path / "synthetic_10000_rows.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "BenchSheet"

    ws.append(["TIMESTAMP", "PRESSURE", "TEMPERATURE", "STATUS"])
    for i in range(10_000):
        ws.append(["2025-01-01T00:00:00Z", float(i), float(i * 1.5), "OK"])
    wb.save(bench_file)

    calamine_reader = CalamineReader()
    openpyxl_reader = OpenpyxlReader()

    # Time Calamine
    t0 = time.perf_counter()
    c_count = sum(
        len(batch)
        for batch in calamine_reader.extract_sheet_cells(bench_file, "BenchSheet")
    )
    calamine_duration = time.perf_counter() - t0

    # Time Openpyxl
    t0 = time.perf_counter()
    o_count = sum(
        len(batch)
        for batch in openpyxl_reader.extract_sheet_cells(bench_file, "BenchSheet")
    )
    openpyxl_duration = time.perf_counter() - t0

    assert c_count == o_count
    assert c_count == 40_004

    ratio = calamine_duration / openpyxl_duration
    msg = (
        f"Calamine took {calamine_duration:.4f}s vs Openpyxl {openpyxl_duration:.4f}s "
        f"(ratio {ratio:.3f} >= 0.5)"
    )
    assert ratio < 0.5, msg
