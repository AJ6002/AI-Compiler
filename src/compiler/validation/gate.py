"""Client validation gate orchestrating quality, contract compliance, and acceptance routing."""

from __future__ import annotations

import uuid

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import ErrorSeverity, JobResultState
from src.compiler.contracts.signals import SignalDictionary
from src.compiler.contracts.validation import ValidationErrorItem, ValidationReport
from src.compiler.execution.executor import ExecutionResult
from src.compiler.structure.types import DiscoveredLayout
from src.compiler.validation.asset_validator import validate_asset_roster
from src.compiler.validation.reconciliation_validator import validate_reconciliation_integrity
from src.compiler.validation.signal_validator import validate_signals_and_units
from src.compiler.validation.temporal_validator import validate_temporal_characteristics


class ClientValidationGate:
    """Evaluates executed datasets against ClientContracts and issues acceptance verdicts."""

    def validate(
        self,
        execution_result: ExecutionResult,
        contract: ClientContract,
        target_object_id: str,
        discovered_layout: DiscoveredLayout | None = None,
        signal_dictionary: SignalDictionary | None = None,
    ) -> ValidationReport:
        """Run all contract and structural checks and return an immutable ValidationReport."""
        all_errors: list[ValidationErrorItem] = []
        all_warnings: list[ValidationErrorItem] = []

        # 1. Reconciliation & cardinality integrity
        r_errors, r_warnings = validate_reconciliation_integrity(execution_result.reconciliation)
        all_errors.extend(r_errors)
        all_warnings.extend(r_warnings)

        # 2. Signal presence & allowed units
        s_errors, s_warnings, coverage = validate_signals_and_units(
            measurements=execution_result.measurements_table,
            contract=contract,
            layout=discovered_layout,
        )
        all_errors.extend(s_errors)
        all_warnings.extend(s_warnings)

        # 3. Temporal, timezone, and cadence compliance
        t_errors, t_warnings = validate_temporal_characteristics(
            measurements=execution_result.measurements_table,
            contract=contract,
        )
        all_errors.extend(t_errors)
        all_warnings.extend(t_warnings)

        # 4. Asset roster compliance
        a_errors, a_warnings = validate_asset_roster(
            measurements=execution_result.measurements_table,
            contract=contract,
        )
        all_errors.extend(a_errors)
        all_warnings.extend(a_warnings)

        # Determine verdict: any FATAL or ERROR severity forces REVIEW_REQUIRED
        has_blocking_errors = any(
            e.severity in (ErrorSeverity.FATAL, ErrorSeverity.ERROR) for e in all_errors
        )
        result_state = (
            JobResultState.REVIEW_REQUIRED if has_blocking_errors else JobResultState.ACCEPTED
        )

        summary_metrics = {
            "total_emitted_records": execution_result.reconciliation.actual_emitted_records,
            "total_data_rows": execution_result.reconciliation.data_rows_processed,
            "total_signals": execution_result.reconciliation.signals_unpivoted,
            "null_value_count": execution_result.reconciliation.null_value_count,
            "signal_coverage": coverage,
            "reconciliation_hash": execution_result.reconciliation.reconciliation_hash,
            "error_count": len(all_errors),
            "warning_count": len(all_warnings),
        }

        report_id = f"val_rpt_{uuid.uuid4().hex[:12]}"

        return ValidationReport(
            tenant_id=contract.tenant_id,
            project_id=contract.project_id,
            report_id=report_id,
            target_object_id=target_object_id,
            result_state=result_state,
            errors=all_errors,
            warnings=all_warnings,
            summary_metrics=summary_metrics,
        )
