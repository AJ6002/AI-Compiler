"""Reconciliation metrics and Cartesian multiplicity validation."""

from __future__ import annotations

from src.compiler.contracts.enums import ErrorCode, ErrorSeverity
from src.compiler.contracts.validation import ValidationErrorItem
from src.compiler.execution.executor import ExecutionReconciliation


def validate_reconciliation_integrity(
    reconciliation: ExecutionReconciliation,
) -> tuple[list[ValidationErrorItem], list[ValidationErrorItem]]:
    """Verify that actual emitted record counts match mathematical expectation.

    Guarantees zero unnotified row drops and zero Cartesian product multiplication.
    Returns (errors, warnings).
    """
    errors: list[ValidationErrorItem] = []
    warnings: list[ValidationErrorItem] = []

    # 1. Cartesian product / row multiplication check
    if reconciliation.actual_emitted_records != reconciliation.expected_emitted_records:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_EXEC_ROW_MULTIPLICATION,
                severity=ErrorSeverity.FATAL,
                message=(
                    f"Reconciliation failure: expected {reconciliation.expected_emitted_records} "
                    f"records (data_rows={reconciliation.data_rows_processed} * "
                    f"signals={reconciliation.signals_unpivoted}), but emitted "
                    f"{reconciliation.actual_emitted_records} records."
                ),
                remediation="Internal compiler error: unpivot Cartesian multiplication detected.",
            )
        )

    # 2. Empty dataset check
    if reconciliation.data_rows_processed == 0 or reconciliation.actual_emitted_records == 0:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                severity=ErrorSeverity.ERROR,
                message="Extracted dataset contains zero data rows.",
                remediation=(
                    "Inspect spreadsheet structure and ensure region boundaries contain data."
                ),
            )
        )

    return errors, warnings
