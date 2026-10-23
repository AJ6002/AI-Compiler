"""Unit tests for OpenpyxlReader and structural spreadsheet extraction."""

from pathlib import Path

import pytest

from src.compiler.contracts.enums import DateEpoch
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


@pytest.fixture
def reader() -> OpenpyxlReader:
    return OpenpyxlReader()


def test_probe_simple_workbook(reader: OpenpyxlReader, fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    probe_result = reader.probe(xlsx_path)

    assert probe_result.sheet_count == 1
    assert "SimpleReadings" in probe_result.sheet_names
    assert probe_result.date_epoch == "1900"
    assert not probe_result.is_macro_enabled
    max_row, max_col = probe_result.dimensions_map["SimpleReadings"]
    assert max_row == 51
    assert max_col == 9


def test_probe_from_bytes(reader: OpenpyxlReader, fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    raw_bytes = xlsx_path.read_bytes()
    probe_result = reader.probe(raw_bytes)

    assert probe_result.sheet_count == 1
    assert "SimpleReadings" in probe_result.sheet_names


def test_inspect_merged_headers(reader: OpenpyxlReader, fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-test",
        project_id="proj-test",
        max_preview_rows=10,
    )

    assert structure.tenant_id == "tenant-test"
    assert structure.project_id == "proj-test"
    assert structure.workbook_name == "merged_equipment_headers.xlsx"
    assert structure.date_epoch == DateEpoch.EPOCH_1900
    assert len(structure.sheets) == 1

    sheet = structure.sheets[0]
    assert sheet.name == "MergedHeaders"
    assert "B1:C1" in sheet.merged_ranges
    assert "D1:E1" in sheet.merged_ranges

    # Verify merged cell flags in cell samples
    cell_b1 = next(c for c in sheet.cells_sample if c.coordinate == "B1")
    cell_c1 = next(c for c in sheet.cells_sample if c.coordinate == "C1")
    assert cell_b1.is_merged is True
    assert cell_b1.raw_value == "DISPENSER_1"
    assert cell_c1.is_merged is True


def test_extract_sheet_cells_batches(reader: OpenpyxlReader, fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    batches = list(reader.extract_sheet_cells(xlsx_path, "SimpleReadings", batch_size=100))

    assert len(batches) > 0
    total_cells = sum(len(b) for b in batches)
    # 51 rows * 9 columns = 459 cells
    assert total_cells == 51 * 9

    # Verify first row headers
    first_cell = batches[0][0]
    assert first_cell.coordinate == "A1"
    assert first_cell.raw_value == "DATE"


def test_extract_sheet_invalid_sheet_name(reader: OpenpyxlReader, fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    with pytest.raises(KeyError, match="Sheet 'NonExistent' not found"):
        list(reader.extract_sheet_cells(xlsx_path, "NonExistent"))
