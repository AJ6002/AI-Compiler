"""Unit tests for BatchAssembler multi-file union and partial-batch policy enforcement."""

from datetime import UTC, datetime

import pyarrow as pa

from src.compiler.batch.assembler import BatchAssembler
from src.compiler.batch.types import FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import JobResultState, PartialBatchPolicy
from src.compiler.contracts.validation import ValidationReport
from src.compiler.execution.executor import (
    MEASUREMENT_ARROW_SCHEMA,
    ExecutionReconciliation,
    ExecutionResult,
)
from src.compiler.execution.provenance import PROVENANCE_ARROW_SCHEMA


def _make_dummy_contract(
    expected_assets: list[str],
    policy: PartialBatchPolicy = PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
) -> ClientContract:
    return ClientContract(
        contract_id="contract_test",
        tenant_id="tenant_a",
        project_id="proj_1",
        version="1.0.0",
        expected_assets=expected_assets,
        required_signals=["PRESSURE", "TEMP"],
        allowed_units={"PRESSURE": ["bar", "psi"], "TEMP": ["C", "F"]},
        timezone="UTC",
        partial_batch_policy=policy,
    )


def _make_dummy_outcome(
    filename: str,
    asset_id: str,
    state: JobResultState,
    row_count: int = 10,
) -> FileProcessingOutcome:
    report = ValidationReport(
        report_id=f"rep_{filename}",
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id=f"obj_{filename}",
        result_state=state,
    )

    exec_result: ExecutionResult | None = None
    if state == JobResultState.ACCEPTED:
        # Build dummy measurement and provenance tables
        meas_data = {
            "observation_key": [f"key_{i}" for i in range(row_count)],
            "tenant_id": ["tenant_a"] * row_count,
            "project_id": ["proj_1"] * row_count,
            "asset_id": [asset_id] * row_count,
            "timestamp_utc": [datetime(2026, 4, 1, 10, i, 0, tzinfo=UTC) for i in range(row_count)],
            "signal_id": ["PRESSURE"] * row_count,
            "value": [100.0 + i for i in range(row_count)],
            "raw_source_row": list(range(1, row_count + 1)),
            "source_file": [filename] * row_count,
        }
        meas_tbl = pa.Table.from_pydict(meas_data, schema=MEASUREMENT_ARROW_SCHEMA)

        prov_data = {
            "observation_key": [f"key_{i}" for i in range(row_count)],
            "signal_id": ["PRESSURE"] * row_count,
            "source_file": [filename] * row_count,
            "sheet_name": ["Sheet1"] * row_count,
            "cell_coordinate": [f"B{i + 2}" for i in range(row_count)],
            "raw_value": [str(100.0 + i) for i in range(row_count)],
            "formula": [None] * row_count,
            "transform_ref": ["literal"] * row_count,
        }
        prov_tbl = pa.Table.from_pydict(prov_data, schema=PROVENANCE_ARROW_SCHEMA)

        reconciliation = ExecutionReconciliation(
            extracted_source_rows=row_count,
            data_rows_processed=row_count,
            signals_unpivoted=1,
            expected_emitted_records=row_count,
            actual_emitted_records=row_count,
            reconciliation_hash="hash_dummy",
        )
        exec_result = ExecutionResult(
            measurements_table=meas_tbl,
            provenance_table=prov_tbl,
            reconciliation=reconciliation,
        )

    return FileProcessingOutcome(
        filename=filename,
        object_id=f"obj_{filename}",
        sha256=f"sha_{filename}",
        result_state=state,
        validation_report=report,
        execution_result=exec_result,
        asset_id=asset_id,
    )


def test_clean_batch_union_all_accepted():
    """Verify that a batch with all accepted files unions rows cleanly with zero data loss."""
    contract = _make_dummy_contract(expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"])
    outcomes = [
        _make_dummy_outcome("comp_1.xlsx", "COMP_1", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_2.xlsx", "COMP_2", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_3.xlsx", "COMP_3", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_4.xlsx", "COMP_4", JobResultState.ACCEPTED, row_count=20),
    ]

    assembler = BatchAssembler()
    result = assembler.assemble(batch_id="batch_clean_1", contract=contract, outcomes=outcomes)

    assert result.result_state == JobResultState.ACCEPTED
    assert result.batch_measurements_table is not None
    assert result.batch_provenance_table is not None
    # 4 files * 20 rows = 80 rows total
    assert result.batch_measurements_table.num_rows == 80
    assert result.batch_provenance_table.num_rows == 80
    assert result.batch_validation_report.files_accepted == 4
    assert result.batch_validation_report.files_review_required == 0
    assert len(result.batch_validation_report.files_missing) == 0


def test_mixed_batch_publish_accepted_flag_review():
    """Under PUBLISH_ACCEPTED_FLAG_REVIEW, 4 accepted files are published and 1 flags review."""
    contract = _make_dummy_contract(
        expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
        policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )
    outcomes = [
        _make_dummy_outcome("comp_1.xlsx", "COMP_1", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_2.xlsx", "COMP_2", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_3.xlsx", "COMP_3", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_4.xlsx", "COMP_4", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_5_defective.xlsx", "COMP_5", JobResultState.REVIEW_REQUIRED),
    ]

    assembler = BatchAssembler()
    result = assembler.assemble(batch_id="batch_mixed_1", contract=contract, outcomes=outcomes)

    # Batch verdict is REVIEW_REQUIRED due to the 5th file
    assert result.result_state == JobResultState.REVIEW_REQUIRED
    assert result.batch_validation_report.files_accepted == 4
    assert result.batch_validation_report.files_review_required == 1

    # But accepted tables ARE published (80 rows)
    assert result.batch_measurements_table is not None
    assert result.batch_measurements_table.num_rows == 80
    assert result.batch_provenance_table is not None
    assert result.batch_provenance_table.num_rows == 80


def test_mixed_batch_block_entire_batch():
    """Under BLOCK_ENTIRE_BATCH, a defective file suppresses table publication entirely."""
    contract = _make_dummy_contract(
        expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
        policy=PartialBatchPolicy.BLOCK_ENTIRE_BATCH,
    )
    outcomes = [
        _make_dummy_outcome("comp_1.xlsx", "COMP_1", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_2.xlsx", "COMP_2", JobResultState.ACCEPTED, row_count=20),
        _make_dummy_outcome("comp_3_bad.xlsx", "COMP_3", JobResultState.REVIEW_REQUIRED),
    ]

    assembler = BatchAssembler()
    result = assembler.assemble(batch_id="batch_aon_1", contract=contract, outcomes=outcomes)

    assert result.result_state == JobResultState.REVIEW_REQUIRED
    assert result.batch_measurements_table is None
    assert result.batch_provenance_table is None
    assert result.batch_validation_report.files_accepted == 2
    assert result.batch_validation_report.files_review_required == 1
