"""Unit tests for BatchReconciler conflict detection and asset roster completeness."""

from datetime import UTC, datetime

import pyarrow as pa

from src.compiler.batch.reconciler import BatchReconciler
from src.compiler.batch.types import FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.contracts.validation import ValidationReport
from src.compiler.execution.executor import (
    MEASUREMENT_ARROW_SCHEMA,
    ExecutionReconciliation,
    ExecutionResult,
)
from src.compiler.execution.provenance import PROVENANCE_ARROW_SCHEMA


def _make_contract(expected_assets: list[str]) -> ClientContract:
    return ClientContract(
        contract_id="contract_reconcile",
        tenant_id="tenant_a",
        project_id="proj_1",
        version="1.0.0",
        expected_assets=expected_assets,
        required_signals=["PRESSURE"],
        allowed_units={"PRESSURE": ["bar"]},
        timezone="UTC",
    )


def _make_table(rows: list[dict]) -> pa.Table:
    return pa.Table.from_pydict(
        {
            "observation_key": [r["key"] for r in rows],
            "tenant_id": ["tenant_a"] * len(rows),
            "project_id": ["proj_1"] * len(rows),
            "asset_id": [r["asset"] for r in rows],
            "timestamp_utc": [r["time"] for r in rows],
            "signal_id": [r["signal"] for r in rows],
            "value": [r["value"] for r in rows],
            "raw_source_row": [1] * len(rows),
            "source_file": [r["file"] for r in rows],
        },
        schema=MEASUREMENT_ARROW_SCHEMA,
    )


def _make_outcome(filename: str, rows: list[dict]) -> FileProcessingOutcome:
    tbl = _make_table(rows)
    prov_tbl = pa.Table.from_pydict(
        {
            "observation_key": [r["key"] for r in rows],
            "signal_id": [r["signal"] for r in rows],
            "source_file": [filename] * len(rows),
            "sheet_name": ["Sheet1"] * len(rows),
            "cell_coordinate": ["B2"] * len(rows),
            "raw_value": [str(r["value"]) for r in rows],
            "formula": [None] * len(rows),
            "transform_ref": ["literal"] * len(rows),
        },
        schema=PROVENANCE_ARROW_SCHEMA,
    )
    exec_result = ExecutionResult(
        measurements_table=tbl,
        provenance_table=prov_tbl,
        reconciliation=ExecutionReconciliation(
            extracted_source_rows=len(rows),
            data_rows_processed=len(rows),
            signals_unpivoted=1,
            expected_emitted_records=len(rows),
            actual_emitted_records=len(rows),
            reconciliation_hash="hash",
        ),
    )
    return FileProcessingOutcome(
        filename=filename,
        object_id=f"obj_{filename}",
        sha256=f"sha_{filename}",
        result_state=JobResultState.ACCEPTED,
        validation_report=ValidationReport(
            report_id=f"rep_{filename}",
            tenant_id="tenant_a",
            project_id="proj_1",
            target_object_id=f"obj_{filename}",
            result_state=JobResultState.ACCEPTED,
        ),
        execution_result=exec_result,
        asset_id=rows[0]["asset"] if rows else None,
    )


def test_missing_asset_detection():
    """Verify that omitting an asset named in expected_assets triggers ERR_VAL_MISSING_ASSET."""
    contract = _make_contract(expected_assets=["COMP_1", "COMP_2", "COMP_3"])

    # Provide data for COMP_1 and COMP_2 only
    t = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
    outcomes = [
        _make_outcome(
            "f1.xlsx",
            [
                {
                    "key": "k1",
                    "asset": "COMP_1",
                    "time": t,
                    "signal": "PRESSURE",
                    "value": 10.0,
                    "file": "f1.xlsx",
                }
            ],
        ),
        _make_outcome(
            "f2.xlsx",
            [
                {
                    "key": "k2",
                    "asset": "COMP_2",
                    "time": t,
                    "signal": "PRESSURE",
                    "value": 20.0,
                    "file": "f2.xlsx",
                }
            ],
        ),
    ]

    reconciler = BatchReconciler()
    report = reconciler.reconcile(contract=contract, outcomes=outcomes)

    assert report.has_errors
    assert "COMP_3" in report.missing_assets
    assert any(e.code == ErrorCode.ERR_VAL_MISSING_ASSET for e in report.errors)


def test_cross_file_value_disagreement_detection():
    """Verify conflicting readings across files flag ERR_VAL_CROSS_FILE_DISAGREEMENT."""
    contract = _make_contract(expected_assets=["COMP_1"])
    t = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)

    # File 1 says 100.0 bar, File 2 says 150.0 bar for same asset/signal/timestamp
    f1 = _make_outcome(
        "comp_a.xlsx",
        [
            {
                "key": "k1",
                "asset": "COMP_1",
                "time": t,
                "signal": "PRESSURE",
                "value": 100.0,
                "file": "comp_a.xlsx",
            }
        ],
    )
    f2 = _make_outcome(
        "comp_b.xlsx",
        [
            {
                "key": "k2",
                "asset": "COMP_1",
                "time": t,
                "signal": "PRESSURE",
                "value": 150.0,
                "file": "comp_b.xlsx",
            }
        ],
    )

    reconciler = BatchReconciler()
    report = reconciler.reconcile(contract=contract, outcomes=[f1, f2])

    assert report.has_errors
    assert any(e.code == ErrorCode.ERR_VAL_CROSS_FILE_DISAGREEMENT for e in report.errors)
    conflict_err = next(
        e for e in report.errors if e.code == ErrorCode.ERR_VAL_CROSS_FILE_DISAGREEMENT
    )
    assert "100.0" in conflict_err.message
    assert "150.0" in conflict_err.message


def test_cross_file_identical_reading_no_conflict():
    """Identical sensor readings across files do not trigger conflict errors."""
    contract = _make_contract(expected_assets=["COMP_1"])
    t = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)

    # Both files report 100.0 bar
    f1 = _make_outcome(
        "comp_a.xlsx",
        [
            {
                "key": "k1",
                "asset": "COMP_1",
                "time": t,
                "signal": "PRESSURE",
                "value": 100.0,
                "file": "comp_a.xlsx",
            }
        ],
    )
    f2 = _make_outcome(
        "comp_b.xlsx",
        [
            {
                "key": "k2",
                "asset": "COMP_1",
                "time": t,
                "signal": "PRESSURE",
                "value": 100.0,
                "file": "comp_b.xlsx",
            }
        ],
    )

    reconciler = BatchReconciler()
    report = reconciler.reconcile(contract=contract, outcomes=[f1, f2])

    assert not report.has_errors
    assert len(report.missing_assets) == 0
