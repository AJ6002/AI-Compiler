"""Unit tests for InvestigationToolbox bounds, merges, and formula cache."""

import json
from pathlib import Path

import pytest

from src.compiler.investigation.tools import MAX_RANGE_COLS, MAX_RANGE_ROWS, InvestigationToolbox
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_toolbox_list_sheets_and_merges(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=15)

    toolbox = InvestigationToolbox(xlsx_path, structure, reader)

    sheets_res = json.loads(toolbox.execute_tool("list_sheets", {}))
    assert sheets_res["sheets"] == ["MergedHeaders"]

    merges_res = json.loads(toolbox.execute_tool("inspect_merges", {"sheet_name": "MergedHeaders"}))
    assert "B1:C1" in merges_res["merged_ranges"]
    assert "D1:E1" in merges_res["merged_ranges"]


def test_toolbox_inspect_range_bounds_clamped(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=20)

    toolbox = InvestigationToolbox(xlsx_path, structure, reader)

    # Request oversized window (100 rows x 50 cols)
    range_res = json.loads(
        toolbox.execute_tool(
            "inspect_range",
            {
                "sheet_name": "SimpleReadings",
                "min_row": 1,
                "max_row": 100,
                "min_col": 1,
                "max_col": 50,
            },
        )
    )

    clamped = range_res["clamped_window"]
    # Verify bounds are clamped to MAX_RANGE_ROWS and MAX_RANGE_COLS
    assert clamped[1] - clamped[0] + 1 <= MAX_RANGE_ROWS
    assert clamped[3] - clamped[2] + 1 <= MAX_RANGE_COLS


def test_toolbox_inspect_formula_cache(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_formula" / "formula_stale_cache.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=10)

    toolbox = InvestigationToolbox(xlsx_path, structure, reader)

    formula_res = json.loads(
        toolbox.execute_tool(
            "inspect_formula_cache",
            {"sheet_name": "Calculations", "coordinate": "C2"},
        )
    )

    assert formula_res["has_formula"] is True
    assert formula_res["formula"] == "=A2+B2"
    assert formula_res["cached_value"] is None
    assert formula_res["is_cache_missing"] is True


def test_toolbox_propose_parse_plan_validation(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=10)

    toolbox = InvestigationToolbox(xlsx_path, structure, reader)

    # Invalid operation rejected
    invalid_res = json.loads(
        toolbox.execute_tool(
            "propose_parse_plan",
            {
                "sheet_name": "SimpleReadings",
                "operations": [{"op": "arbitrary_eval_code", "params": {}}],
            },
        )
    )
    assert "error" in invalid_res

    # Valid plan accepted
    valid_res = json.loads(
        toolbox.execute_tool(
            "propose_parse_plan",
            {
                "sheet_name": "SimpleReadings",
                "operations": [
                    {
                        "op": "select_region",
                        "params": {"min_row": 1, "max_row": 10, "min_col": 1, "max_col": 5},
                    },
                    {
                        "op": "unpivot",
                        "params": {"id_vars": ["DATE"], "value_vars": ["SUCTION_PRESS"]},
                    },
                ],
            },
        )
    )
    assert valid_res["status"] == "SUCCESS"
    assert toolbox.proposed_plan is not None
