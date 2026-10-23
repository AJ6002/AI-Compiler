"""Unit tests for formula inspection, cache isolation, and duration parsing."""

import datetime
from pathlib import Path

import pytest

from src.compiler.readers.date_duration import (
    is_duration_format,
    parse_duration_to_seconds,
    parse_excel_date,
)
from src.compiler.readers.formula_handler import (
    extract_external_references,
    inspect_formula_cell,
)
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_is_duration_format() -> None:
    assert is_duration_format("[h]:mm:ss") is True
    assert is_duration_format("[hh]:mm:ss") is True
    assert is_duration_format("[m]:ss") is True
    assert is_duration_format("[s]") is True
    assert is_duration_format("yyyy-mm-dd") is False
    assert is_duration_format("hh:mm:ss") is False
    assert is_duration_format(None) is False


def test_parse_duration_to_seconds_numeric() -> None:
    # 1.0 day = 86400 seconds
    assert parse_duration_to_seconds(1.0) == 86400.0
    # 0.5 days = 12 hours = 43200 seconds
    assert parse_duration_to_seconds(0.5) == 43200.0
    # 1.5 days = 36 hours = 129600 seconds
    assert parse_duration_to_seconds(1.5) == 129600.0


def test_parse_duration_to_seconds_string() -> None:
    # "36:15:00" = 36 * 3600 + 15 * 60 = 129600 + 900 = 130500.0
    assert parse_duration_to_seconds("36:15:00") == 130500.0
    # "12:30" (mm:ss) = 12 * 60 + 30 = 750.0
    assert parse_duration_to_seconds("12:30") == 750.0
    # None on invalid string
    assert parse_duration_to_seconds("invalid") is None
    assert parse_duration_to_seconds(None) is None


def test_parse_excel_date() -> None:
    # 1900 epoch: day 1 is 1900-01-01
    dt_1900 = parse_excel_date(1, date_epoch="1900")
    assert isinstance(dt_1900, datetime.datetime)
    assert dt_1900.year == 1900
    assert dt_1900.month == 1
    assert dt_1900.day == 1

    # 1904 epoch: day 0 is 1904-01-01
    dt_1904 = parse_excel_date(0, date_epoch="1904")
    assert isinstance(dt_1904, datetime.datetime)
    assert dt_1904.year == 1904
    assert dt_1904.month == 1
    assert dt_1904.day == 1


def test_inspect_formula_cell_valid_cache() -> None:
    inspection = inspect_formula_cell("=A1+B1", 42.0)
    assert inspection.has_formula is True
    assert inspection.formula_text == "=A1+B1"
    assert inspection.cached_value == 42.0
    assert inspection.is_cache_missing is False
    assert inspection.has_external_reference is False


def test_inspect_formula_cell_missing_cache() -> None:
    inspection = inspect_formula_cell("=SUM(A1:A10)", None)
    assert inspection.has_formula is True
    assert inspection.formula_text == "=SUM(A1:A10)"
    assert inspection.cached_value is None
    assert inspection.is_cache_missing is True


def test_extract_external_references() -> None:
    formula = "='[External_2025.xlsx]Sheet1'!$A$1 + [2]Data!B5"
    targets = extract_external_references(formula)
    assert targets == ["External_2025.xlsx", "2"]

    inspection = inspect_formula_cell(formula, 100.0)
    assert inspection.has_external_reference is True
    assert "External_2025.xlsx" in inspection.external_targets


def test_inspect_formula_stale_fixture(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_formula" / "formula_stale_cache.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(
        source=xlsx_path,
        tenant_id="tenant-formula",
        project_id="proj-formula",
        max_preview_rows=10,
    )

    sheet = structure.sheets[0]
    formula_cells = [c for c in sheet.cells_sample if c.data_type == "f"]
    assert len(formula_cells) > 0

    # Synthetic fixture has no cached evaluation (openpyxl created it without running excel)
    for c in formula_cells:
        assert c.formula is not None
        assert c.formula.startswith("=")
        assert c.cached_value is None
