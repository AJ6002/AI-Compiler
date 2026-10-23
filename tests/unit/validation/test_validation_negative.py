"""Negative sensitivity tests for ClientValidationGate (blocking damaged/invalid files)."""

from pathlib import Path

import pytest

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import (
    DuplicatePolicy,
    ErrorCode,
    ErrorSeverity,
    JobResultState,
    PartialBatchPolicy,
)
from src.compiler.execution.executor import ExecutionReconciliation, ExecutionResult, PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.structure.types import MetadataEntry
from src.compiler.validation.gate import ClientValidationGate


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


@pytest.fixture
def base_setup(fixtures_dir: Path):
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-neg", "proj-neg", max_preview_rows=15)
    discovery_engine = RuleBasedDiscoveryEngine()
    layout = discovery_engine.discover_sheet(structure.sheets[0])
    compiler = PlanCompiler()
    plan = compiler.compile(layout, "tenant-neg", "proj-neg")
    executor = PlanExecutor(reader=reader)
    exec_result = executor.execute(xlsx_path, plan)
    return exec_result, layout


def test_missing_required_signal_blocks_acceptance(base_setup) -> None:
    exec_result, layout = base_setup

    contract = ClientContract(
        tenant_id="tenant-neg",
        project_id="proj-neg",
        contract_id="contract-neg-01",
        version="1.0.0",
        expected_assets=["COMP_A"],
        required_signals=["SUCTION_PRESS", "NON_EXISTENT_VIBRATION"],
        allowed_units={},
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(exec_result, contract, "obj_missing_sig", layout)

    assert report.result_state == JobResultState.REVIEW_REQUIRED
    error_codes = [e.code for e in report.errors]
    assert ErrorCode.ERR_VAL_MISSING_SIGNAL in error_codes
    assert report.summary_metrics["signal_coverage"]["NON_EXISTENT_VIBRATION"] == 0.0


def test_unapproved_unit_blocks_acceptance(base_setup) -> None:
    exec_result, layout = base_setup

    # Add a metadata entry with an unapproved unit
    unapproved_meta = MetadataEntry(
        key="Pressure Unit:",
        value="psi_unapproved",
        key_coordinate="A1",
    )
    layout_with_meta = layout.model_copy(update={"metadata_entries": [unapproved_meta]})

    contract = ClientContract(
        tenant_id="tenant-neg",
        project_id="proj-neg",
        contract_id="contract-neg-02",
        version="1.0.0",
        expected_assets=["COMP_A"],
        required_signals=["SUCTION_PRESS"],
        allowed_units={"SUCTION_PRESS": ["bar", "kpa"]},
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(exec_result, contract, "obj_unit", layout_with_meta)

    assert report.result_state == JobResultState.REVIEW_REQUIRED
    error_codes = [e.code for e in report.errors]
    assert ErrorCode.ERR_VAL_UNRESOLVED_UNIT in error_codes


def test_unexpected_asset_blocks_acceptance(base_setup) -> None:
    exec_result, layout = base_setup

    # Contract expects COMP_Z, but data has COMP_A
    contract = ClientContract(
        tenant_id="tenant-neg",
        project_id="proj-neg",
        contract_id="contract-neg-03",
        version="1.0.0",
        expected_assets=["COMP_Z"],
        required_signals=["SUCTION_PRESS"],
        allowed_units={},
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(exec_result, contract, "obj_asset", layout)

    assert report.result_state == JobResultState.REVIEW_REQUIRED
    error_codes = [e.code for e in report.errors]
    assert ErrorCode.ERR_VAL_MISSING_ASSET in error_codes


def test_cadence_irregularity_warning(base_setup) -> None:
    exec_result, layout = base_setup

    # Set expected cadence to 10 seconds on hourly data (3600s interval)
    contract = ClientContract(
        tenant_id="tenant-neg",
        project_id="proj-neg",
        contract_id="contract-neg-04",
        version="1.0.0",
        expected_assets=["COMP_A"],
        required_signals=["SUCTION_PRESS"],
        allowed_units={},
        expected_cadence_seconds=10,
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(exec_result, contract, "obj_cadence", layout)

    # Cadence irregularity creates a warning
    warning_codes = [w.code for w in report.warnings]
    assert ErrorCode.ERR_VAL_CADENCE_IRREGULAR in warning_codes


def test_reconciliation_multiplication_blocks_acceptance(base_setup) -> None:
    exec_result, layout = base_setup

    # Corrupt reconciliation to simulate unpivot Cartesian row multiplication
    corrupt_reconciliation = ExecutionReconciliation(
        extracted_source_rows=exec_result.reconciliation.extracted_source_rows,
        data_rows_processed=50,
        signals_unpivoted=6,
        expected_emitted_records=300,
        actual_emitted_records=600,  # Row multiplication!
        null_value_count=0,
        reconciliation_hash="dummy_hash",
    )
    corrupted_result = ExecutionResult(
        measurements_table=exec_result.measurements_table,
        provenance_table=exec_result.provenance_table,
        reconciliation=corrupt_reconciliation,
    )

    contract = ClientContract(
        tenant_id="tenant-neg",
        project_id="proj-neg",
        contract_id="contract-neg-05",
        version="1.0.0",
        expected_assets=["COMP_A"],
        required_signals=["SUCTION_PRESS"],
        allowed_units={},
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(corrupted_result, contract, "obj_multiplication", layout)

    assert report.result_state == JobResultState.REVIEW_REQUIRED
    fatal_errors = [e for e in report.errors if e.severity == ErrorSeverity.FATAL]
    assert len(fatal_errors) > 0
    assert fatal_errors[0].code == ErrorCode.ERR_EXEC_ROW_MULTIPLICATION
