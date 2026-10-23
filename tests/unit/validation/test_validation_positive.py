"""Positive validation tests for ClientValidationGate."""

from pathlib import Path

import pytest

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import DuplicatePolicy, JobResultState, PartialBatchPolicy
from src.compiler.execution.executor import PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.validation.gate import ClientValidationGate


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_validation_gate_accepts_clean_dataset(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-val", "proj-val", max_preview_rows=15)

    discovery_engine = RuleBasedDiscoveryEngine()
    layout = discovery_engine.discover_sheet(structure.sheets[0])

    compiler = PlanCompiler()
    plan = compiler.compile(layout, "tenant-val", "proj-val")

    executor = PlanExecutor(reader=reader)
    exec_result = executor.execute(xlsx_path, plan)

    contract = ClientContract(
        tenant_id="tenant-val",
        project_id="proj-val",
        contract_id="contract-simple-01",
        version="1.0.0",
        expected_assets=["COMP_A"],
        required_signals=["SUCTION_PRESS", "DISCHARGE_PRESS", "OIL_PRESS"],
        optional_signals=["RPM", "STAGE1_TEMP", "STAGE2_TEMP"],
        allowed_units={
            "SUCTION_PRESS": ["bar", "psi"],
            "DISCHARGE_PRESS": ["bar", "psi"],
        },
        timezone="UTC",
        expected_cadence_seconds=3600,
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    gate = ClientValidationGate()
    report = gate.validate(
        execution_result=exec_result,
        contract=contract,
        target_object_id="obj_simple_table",
        discovered_layout=layout,
    )

    assert report.result_state == JobResultState.ACCEPTED
    assert len(report.errors) == 0
    assert report.summary_metrics["total_emitted_records"] == 300
    assert report.summary_metrics["signal_coverage"]["SUCTION_PRESS"] == 1.0
