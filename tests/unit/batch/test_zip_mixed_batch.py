"""Golden integration test for Phase 9.5: Multi-file ZIP batch assembly and partial publication.

Evaluates batch_5_compressors.zip containing 4 valid compressor workbooks and 1 defective file.
Verifies partial-batch policy PUBLISH_ACCEPTED_FLAG_REVIEW.
"""

import zipfile
from pathlib import Path

import pytest

from src.compiler.batch.assembler import BatchAssembler
from src.compiler.batch.types import FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import (
    ErrorCode,
    ErrorSeverity,
    JobResultState,
    PartialBatchPolicy,
)
from src.compiler.contracts.validation import ValidationErrorItem, ValidationReport
from src.compiler.execution.executor import PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.validation.gate import ClientValidationGate


@pytest.fixture
def compressor_contract() -> ClientContract:
    return ClientContract(
        contract_id="contract_compressor_fleet",
        tenant_id="tenant_oil_gas",
        project_id="proj_station_4",
        version="1.0.0",
        expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
        required_signals=["PRESSURE", "TEMP"],
        allowed_units={"PRESSURE": ["bar", "psi"], "TEMP": ["C", "F"]},
        timezone="UTC",
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )


def test_batch_5_compressors_mixed_outcomes(compressor_contract: ClientContract):
    """Process batch_5_compressors.zip end-to-end through Reader, Executor, and Validation."""
    fixture_path = (
        Path(__file__).parent.parent.parent
        / "golden"
        / "fixtures"
        / "zip_mixed"
        / "batch_5_compressors.zip"
    )
    assert fixture_path.exists(), f"Golden fixture missing at {fixture_path}"

    reader = OpenpyxlReader()
    discovery = RuleBasedDiscoveryEngine()
    compiler = PlanCompiler()
    executor = PlanExecutor(reader=reader)
    gate = ClientValidationGate()

    outcomes: list[FileProcessingOutcome] = []

    with zipfile.ZipFile(fixture_path, "r") as zf:
        namelist = sorted(zf.namelist())
        assert len(namelist) == 5, f"Expected 5 files in archive, found {len(namelist)}"

        for filename in namelist:
            raw_bytes = zf.read(filename)

            # 1. Inspect workbook structure and discover layout
            structure = reader.inspect(
                source=raw_bytes,
                tenant_id=compressor_contract.tenant_id,
                project_id=compressor_contract.project_id,
                workbook_name=filename,
            )
            sheet_struct = structure.sheets[0]
            layout = discovery.discover_sheet(sheet_struct)

            # Check if workbook has valid tables
            if not layout.tables or layout.verdict != JobResultState.ACCEPTED:
                # Defective file
                report = ValidationReport(
                    report_id=f"rep_{filename}",
                    tenant_id=compressor_contract.tenant_id,
                    project_id=compressor_contract.project_id,
                    target_object_id=filename,
                    result_state=JobResultState.REVIEW_REQUIRED,
                    errors=[
                        ValidationErrorItem(
                            code=ErrorCode.ERR_STRUCT_DISPERSED_REGIONS,
                            severity=ErrorSeverity.ERROR,
                            message=f"No valid data table detected in '{filename}'.",
                            remediation="Review defective sheet structure.",
                        )
                    ],
                )
                outcomes.append(
                    FileProcessingOutcome(
                        filename=filename,
                        object_id=f"obj_{filename}",
                        sha256=f"sha_{filename}",
                        result_state=JobResultState.REVIEW_REQUIRED,
                        validation_report=report,
                    )
                )
            else:
                # 2. Compile plan using sheet name as asset identifier
                asset_id = layout.sheet_name
                plan = compiler.compile(
                    layout=layout,
                    tenant_id=compressor_contract.tenant_id,
                    project_id=compressor_contract.project_id,
                    default_asset_id=asset_id,
                )

                # 3. Execute plan
                exec_result = executor.execute(
                    source=raw_bytes,
                    plan=plan,
                    source_filename=filename,
                    default_asset_id=asset_id,
                )

                # 4. Validate output
                val_report = gate.validate(
                    execution_result=exec_result,
                    contract=compressor_contract,
                    target_object_id=filename,
                    discovered_layout=layout,
                )

                outcomes.append(
                    FileProcessingOutcome(
                        filename=filename,
                        object_id=f"obj_{filename}",
                        sha256=f"sha_{filename}",
                        result_state=val_report.result_state,
                        validation_report=val_report,
                        execution_result=exec_result,
                        asset_id=asset_id,
                    )
                )

    # 5. Assemble batch with BatchAssembler
    assembler = BatchAssembler()
    result = assembler.assemble(
        batch_id="batch_compressor_station_4",
        contract=compressor_contract,
        outcomes=outcomes,
    )

    # Acceptance Criteria Assertions:
    # 1. 5 files evaluated
    assert result.batch_validation_report.files_found == 5
    # 2. 4 valid compressor workbooks accepted
    assert result.batch_validation_report.files_accepted == 4
    # 3. 1 defective workbook held back for review
    assert result.batch_validation_report.files_review_required == 1
    # 4. Overall batch verdict is REVIEW_REQUIRED
    assert result.result_state == JobResultState.REVIEW_REQUIRED
    assert result.batch_validation_report.result_state == JobResultState.REVIEW_REQUIRED

    # 5. Partial publication: 4 accepted files published to batch Parquet
    assert result.batch_measurements_table is not None
    assert result.batch_provenance_table is not None

    # Each accepted file has 20 timestamps * 2 signals (PRESSURE, TEMP) = 40 rows
    # 4 files * 40 rows = 160 rows total in batch measurements table
    assert result.batch_measurements_table.num_rows == 160
    assert result.batch_provenance_table.num_rows == 160

    # 6. All 4 expected assets are present in the accepted data
    assets_present = set(result.batch_measurements_table.column("asset_id").to_pylist())
    assert assets_present == {"COMP_1", "COMP_2", "COMP_3", "COMP_4"}
    assert len(result.batch_validation_report.files_missing) == 0

    # 7. Defective file error is captured in batch report
    assert any(
        "compressor_log_defective.xlsx" in str(e.message) or "No valid data table" in str(e.message)
        for e in result.batch_validation_report.batch_errors
    )
