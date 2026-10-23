"""Batch Assembler combining accepted per-file tables into unified Arrow datasets."""

from __future__ import annotations

import pyarrow as pa

from src.compiler.batch.reconciler import BatchReconciler
from src.compiler.batch.types import BatchAssemblyResult, FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import JobResultState, PartialBatchPolicy
from src.compiler.contracts.validation import BatchValidationReport, ValidationErrorItem


class BatchAssembler:
    """Assembles multi-file archives into reconciled datasets enforcing partial-batch policy."""

    def __init__(self, reconciler: BatchReconciler | None = None) -> None:
        self.reconciler = reconciler or BatchReconciler()

    def assemble(
        self,
        batch_id: str,
        contract: ClientContract,
        outcomes: list[FileProcessingOutcome],
    ) -> BatchAssemblyResult:
        """Combine per-file outcomes into a unified batch dataset under contract policies."""
        # 1. Run cross-file reconciliation (asset roster & conflict detection)
        reconciliation = self.reconciler.reconcile(contract=contract, outcomes=outcomes)

        # 2. Compute per-file counts and statuses
        per_file_statuses: dict[str, JobResultState] = {
            o.filename: o.result_state for o in outcomes
        }
        accepted_outcomes = [o for o in outcomes if o.result_state == JobResultState.ACCEPTED]
        review_outcomes = [o for o in outcomes if o.result_state != JobResultState.ACCEPTED]

        files_found = len(outcomes)
        files_accepted = len(accepted_outcomes)
        files_review = len(review_outcomes)
        files_expected = max(files_found, len(contract.expected_assets))

        # 3. Determine overall batch verdict
        has_reconciliation_errors = reconciliation.has_errors
        has_unaccepted_files = files_review > 0

        if not has_unaccepted_files and not has_reconciliation_errors:
            batch_result_state = JobResultState.ACCEPTED
        else:
            batch_result_state = JobResultState.REVIEW_REQUIRED

        # 4. Apply partial-batch publication policy
        batch_measurements: pa.Table | None = None
        batch_provenance: pa.Table | None = None

        all_batch_errors: list[ValidationErrorItem] = list(reconciliation.errors)
        for ro in review_outcomes:
            all_batch_errors.extend(ro.validation_report.errors)

        policy = contract.partial_batch_policy

        if policy == PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW:
            # Union accepted files even if some files require review
            meas_tables: list[pa.Table] = []
            prov_tables: list[pa.Table] = []

            for outcome in accepted_outcomes:
                if outcome.execution_result:
                    if outcome.execution_result.measurements_table is not None:
                        meas_tables.append(outcome.execution_result.measurements_table)
                    if outcome.execution_result.provenance_table is not None:
                        prov_tables.append(outcome.execution_result.provenance_table)

            if meas_tables:
                batch_measurements = pa.concat_tables(meas_tables)
            if prov_tables:
                batch_provenance = pa.concat_tables(prov_tables)

        elif policy == PartialBatchPolicy.BLOCK_ENTIRE_BATCH:
            # In block-entire-batch, publish only if the entire batch is accepted
            if batch_result_state == JobResultState.ACCEPTED:
                meas_tables = [
                    o.execution_result.measurements_table
                    for o in accepted_outcomes
                    if o.execution_result and o.execution_result.measurements_table is not None
                ]
                prov_tables = [
                    o.execution_result.provenance_table
                    for o in accepted_outcomes
                    if o.execution_result and o.execution_result.provenance_table is not None
                ]
                if meas_tables:
                    batch_measurements = pa.concat_tables(meas_tables)
                if prov_tables:
                    batch_provenance = pa.concat_tables(prov_tables)
            else:
                batch_measurements = None
                batch_provenance = None

        # 5. Build immutable BatchValidationReport
        report = BatchValidationReport(
            tenant_id=contract.tenant_id,
            project_id=contract.project_id,
            batch_id=batch_id,
            result_state=batch_result_state,
            files_expected=files_expected,
            files_found=files_found,
            files_accepted=files_accepted,
            files_review_required=files_review,
            files_missing=reconciliation.missing_assets,
            per_file_statuses=per_file_statuses,
            batch_errors=all_batch_errors,
        )

        return BatchAssemblyResult(
            batch_id=batch_id,
            result_state=batch_result_state,
            batch_measurements_table=batch_measurements,
            batch_provenance_table=batch_provenance,
            batch_validation_report=report,
            per_file_outcomes=outcomes,
        )
