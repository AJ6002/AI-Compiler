"""Tests for timestamp resolution in PlanExecutor, verifying composite header handling."""

import datetime
from pathlib import Path

import openpyxl

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.execution.executor import PlanExecutor


def test_date_and_time_single_column(tmp_path: Path) -> None:
    """Verify that a single column named 'DATE & TIME' resolves real timestamps, not epoch."""
    wb_path = tmp_path / "date_and_time_test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Readings"

    # Header row
    ws.append(["DATE & TIME", "ASSET_ID", "PRESSURE", "TEMPERATURE"])
    # Row 1
    ws.append(["2025-11-04 10:30:00", "COMP_01", 12.5, 45.0])
    # Row 2
    ws.append(["2025-11-04 10:35:00", "COMP_01", 12.8, 45.4])
    wb.save(wb_path)

    plan = ParsePlan(
        plan_id="plan-date-time-test",
        tenant_id="tenant-test",
        project_id="proj-test",
        target_sheet="Readings",
        operations=[
            PlanOperation(
                op=PlanOperationType.SELECT_REGION,
                params={"min_row": 1, "max_row": 3, "min_col": 1, "max_col": 4},
            ),
            PlanOperation(
                op=PlanOperationType.FLATTEN_HEADERS,
                params={"header_rows": [1]},
            ),
            PlanOperation(
                op=PlanOperationType.UNPIVOT,
                params={
                    "id_vars": ["DATE & TIME", "ASSET_ID"],
                    "value_vars": ["PRESSURE", "TEMPERATURE"],
                },
            ),
        ],
    )

    executor = PlanExecutor()
    result = executor.execute(wb_path, plan)

    # Assert execution completed and produced records
    assert result.measurements_table.num_rows == 4

    timestamps = result.measurements_table.column("timestamp_utc").to_pylist()
    epoch_default = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)

    # Critical assertion: Neither timestamp should fall back to epoch
    for ts in timestamps:
        assert ts != epoch_default
        assert ts.year == 2025
        assert ts.month == 11
        assert ts.day == 4

    # Assert exact timestamps
    unique_ts = sorted(set(timestamps))
    assert len(unique_ts) == 2
    assert unique_ts[0] == datetime.datetime(2025, 11, 4, 10, 30, tzinfo=datetime.UTC)
    assert unique_ts[1] == datetime.datetime(2025, 11, 4, 10, 35, tzinfo=datetime.UTC)
