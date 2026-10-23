"""Unit tests for allowlisted operations and PlanCompiler."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.plans.operations import (
    SelectRegionParams,
    validate_operation_params,
)
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_validate_operation_params() -> None:
    # Valid parameters
    valid_p = {"min_row": 1, "max_row": 10, "min_col": 1, "max_col": 5}
    model = validate_operation_params(PlanOperationType.SELECT_REGION, valid_p)
    assert isinstance(model, SelectRegionParams)

    # Extra parameters forbidden
    invalid_extra = {"min_row": 1, "max_row": 10, "min_col": 1, "max_col": 5, "extra": "forbidden"}
    with pytest.raises(ValidationError):
        validate_operation_params(PlanOperationType.SELECT_REGION, invalid_extra)


def test_compile_plan_simple_table(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=15)

    discovery_engine = RuleBasedDiscoveryEngine()
    layout = discovery_engine.discover_sheet(structure.sheets[0])

    compiler = PlanCompiler()
    plan = compiler.compile(
        layout=layout,
        tenant_id="tenant-test",
        project_id="proj-test",
    )

    assert plan.target_sheet == "SimpleReadings"
    assert len(plan.operations) >= 4

    op_types = [op.op for op in plan.operations]
    assert PlanOperationType.SELECT_REGION in op_types
    assert PlanOperationType.FLATTEN_HEADERS in op_types
    assert PlanOperationType.FILTER_ROWS in op_types
    assert PlanOperationType.UNPIVOT in op_types

    unpivot_op = next(op for op in plan.operations if op.op == PlanOperationType.UNPIVOT)
    assert "DATE" in unpivot_op.params["id_vars"]
    assert "SUCTION_PRESS" in unpivot_op.params["value_vars"]
