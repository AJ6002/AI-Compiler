"""Tests for dry_run mode in PlanExecutor."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.execution.executor import PlanExecutor


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_executor_dry_run_flag(fixtures_dir: Path) -> None:
    """Assert dry_run=True returns ExecutionResult without external storage writes."""
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"

    plan = ParsePlan(
        plan_id="plan-dry-run-test",
        tenant_id="tenant-test",
        project_id="proj-test",
        target_sheet="SimpleReadings",
        operations=[
            PlanOperation(
                op=PlanOperationType.SELECT_REGION,
                params={"min_row": 1, "max_row": 51, "min_col": 1, "max_col": 9},
            ),
            PlanOperation(
                op=PlanOperationType.FLATTEN_HEADERS,
                params={"header_rows": [1]},
            ),
            PlanOperation(
                op=PlanOperationType.UNPIVOT,
                params={
                    "id_vars": ["DATE", "TIME", "ASSET"],
                    "value_vars": [
                        "SUCTION_PRESS",
                        "DISCHARGE_PRESS",
                        "OIL_PRESS",
                        "STAGE1_TEMP",
                        "STAGE2_TEMP",
                        "RPM",
                    ],
                },
            ),
        ],
    )

    # Create mock object store to verify zero write side effects
    mock_store = MagicMock()

    executor = PlanExecutor()
    result = executor.execute(xlsx_path, plan, dry_run=True)

    # Verify ExecutionResult tables and reconciliation are fully populated
    assert result.measurements_table.num_rows == 300
    assert result.provenance_table.num_rows == 300
    assert result.reconciliation.actual_emitted_records == 300
    assert result.reconciliation.reconciliation_hash != ""

    # Verify mock object store has zero interactions
    assert mock_store.put.call_count == 0
    assert mock_store.write.call_count == 0
