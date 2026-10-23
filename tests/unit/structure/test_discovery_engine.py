"""Unit tests for StructuralDiscoveryEngine and GridGulpAdapter."""

from pathlib import Path

import pytest

from src.compiler.contracts.enums import JobResultState
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.structure.gridgulp_adapter import GridGulpAdapter


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_discover_sheet_simple_table(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-engine",
        project_id="proj-engine",
        max_preview_rows=15,
    )

    engine = RuleBasedDiscoveryEngine()
    layout = engine.discover_sheet(structure.sheets[0])

    assert layout.sheet_name == "SimpleReadings"
    assert layout.verdict == JobResultState.ACCEPTED
    assert len(layout.tables) == 1

    table = layout.tables[0]
    assert table.header_rows == [1]
    assert table.data_start_row == 2
    assert table.data_end_row == 51
    assert len(table.columns) == 9
    assert table.columns[0].path == "DATE"


def test_discover_sheet_complex_merged_headers(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-engine",
        project_id="proj-engine",
        max_preview_rows=25,
    )

    engine = RuleBasedDiscoveryEngine()
    layout = engine.discover_sheet(structure.sheets[0])

    assert layout.sheet_name == "MergedHeaders"
    assert layout.verdict == JobResultState.ACCEPTED
    assert len(layout.tables) == 1

    table = layout.tables[0]
    assert table.header_rows == [1, 2, 3]
    assert table.data_start_row == 4
    assert len(table.columns) == 5

    paths = [c.path for c in table.columns]
    assert "DISPENSER_1.HOSE_A.PRESSURE" in paths
    assert "DISPENSER_2.HOSE_B.TEMPERATURE" in paths


def test_discover_workbook(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_scattered" / "scattered_with_metadata.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-engine",
        project_id="proj-engine",
        max_preview_rows=30,
    )

    engine = RuleBasedDiscoveryEngine()
    layouts = engine.discover_workbook(structure)

    assert len(layouts) == 1
    layout = layouts[0]
    assert layout.sheet_name == "PlantReport"
    assert layout.verdict == JobResultState.ACCEPTED
    assert len(layout.metadata_entries) == 3
    assert len(layout.tables) == 1

    table = layout.tables[0]
    assert table.boundary.min_row == 6
    assert table.header_rows == [6]
    assert table.data_start_row == 7


def test_gridgulp_adapter_fallback(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-engine",
        project_id="proj-engine",
        max_preview_rows=15,
    )

    # When disabled, GridGulpAdapter safely falls back to rule-based engine
    adapter = GridGulpAdapter(enabled=False)
    layout = adapter.discover_sheet(structure.sheets[0])

    assert layout.verdict == JobResultState.ACCEPTED
    assert len(layout.tables) == 1
    assert adapter.PINNED_COMMIT == "e87f1a9c3d4b2e6a"
    assert adapter.LICENSE == "Apache-2.0"
