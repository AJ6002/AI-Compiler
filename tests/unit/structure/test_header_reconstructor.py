"""Unit tests for HeaderReconstructor and hierarchical column path resolution."""

from pathlib import Path

import pytest

from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.header_reconstructor import HeaderReconstructor
from src.compiler.structure.occupancy_grid import OccupancyGrid


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_reconstruct_hierarchical_headers_disambiguation(fixtures_dir: Path) -> None:
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

    reconstructor = HeaderReconstructor(grid)
    # Rows 1, 2, 3 are the header band; cols 1 to 5
    header_paths = reconstructor.reconstruct_headers(
        header_rows=[1, 2, 3],
        min_col=1,
        max_col=5,
    )

    assert len(header_paths) == 5

    paths_by_col = {hp.column_index: hp for hp in header_paths}

    # Col 1: TIMESTAMP.TIME_UTC
    assert "TIME_UTC" in paths_by_col[1].leaf_name

    # Col 2: DISPENSER_1.HOSE_A.PRESSURE
    assert paths_by_col[2].path == "DISPENSER_1.HOSE_A.PRESSURE"
    assert paths_by_col[2].leaf_name == "PRESSURE"
    assert paths_by_col[2].ancestors == ["DISPENSER_1", "HOSE_A"]

    # Col 3: DISPENSER_1.HOSE_B.TEMPERATURE
    assert paths_by_col[3].path == "DISPENSER_1.HOSE_B.TEMPERATURE"
    assert paths_by_col[3].leaf_name == "TEMPERATURE"
    assert paths_by_col[3].ancestors == ["DISPENSER_1", "HOSE_B"]

    # Col 4: DISPENSER_2.HOSE_A.PRESSURE
    assert paths_by_col[4].path == "DISPENSER_2.HOSE_A.PRESSURE"
    assert paths_by_col[4].leaf_name == "PRESSURE"
    assert paths_by_col[4].ancestors == ["DISPENSER_2", "HOSE_A"]

    # Col 5: DISPENSER_2.HOSE_B.TEMPERATURE
    assert paths_by_col[5].path == "DISPENSER_2.HOSE_B.TEMPERATURE"
    assert paths_by_col[5].leaf_name == "TEMPERATURE"
    assert paths_by_col[5].ancestors == ["DISPENSER_2", "HOSE_B"]

    # Crucial assertion: Duplicate leaf names ("PRESSURE" and "TEMPERATURE") are
    # completely disambiguated into 4 unique hierarchical paths!
    all_paths = [hp.path for hp in header_paths]
    assert len(set(all_paths)) == len(all_paths)


def test_reconstruct_simple_single_row_headers(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-simple",
        project_id="proj-simple",
        max_preview_rows=10,
    )

    sheet = structure.sheets[0]
    grid = OccupancyGrid(
        max_row=sheet.max_row,
        max_col=sheet.max_col,
        cells=sheet.cells_sample,
        merged_ranges=sheet.merged_ranges,
    )

    reconstructor = HeaderReconstructor(grid)
    header_paths = reconstructor.reconstruct_headers(
        header_rows=[1],
        min_col=1,
        max_col=9,
    )

    assert len(header_paths) == 9
    path_names = [hp.path for hp in header_paths]
    assert path_names == [
        "DATE",
        "TIME",
        "ASSET",
        "SUCTION_PRESS",
        "DISCHARGE_PRESS",
        "OIL_PRESS",
        "STAGE1_TEMP",
        "STAGE2_TEMP",
        "RPM",
    ]
