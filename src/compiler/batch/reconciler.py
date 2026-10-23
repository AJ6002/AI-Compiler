"""Cross-file batch reconciliation and conflict detection engine.

Detects missing assets against expected rosters and conflicting telemetry
measurements across multi-file submissions without silent overwriting or speculative deduplication.
"""

from __future__ import annotations

from src.compiler.batch.types import FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import ErrorCode, ErrorSeverity, JobResultState
from src.compiler.contracts.validation import ValidationErrorItem


class ReconciliationReport:
    """Findings from cross-file batch reconciliation."""

    def __init__(
        self,
        errors: list[ValidationErrorItem],
        warnings: list[ValidationErrorItem],
        missing_assets: list[str],
        accepted_assets: list[str],
    ) -> None:
        self.errors = errors
        self.warnings = warnings
        self.missing_assets = missing_assets
        self.accepted_assets = accepted_assets

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class BatchReconciler:
    """Reconciles asset rosters and detects conflicting cross-file records."""

    def reconcile(
        self,
        contract: ClientContract,
        outcomes: list[FileProcessingOutcome],
    ) -> ReconciliationReport:
        """Execute cross-file reconciliation across all file outcomes."""
        errors: list[ValidationErrorItem] = []
        warnings: list[ValidationErrorItem] = []

        # 1. Collect assets from accepted files
        accepted_assets: set[str] = set()
        for outcome in outcomes:
            if outcome.result_state == JobResultState.ACCEPTED:
                if outcome.asset_id:
                    accepted_assets.add(outcome.asset_id)
                elif outcome.execution_result and outcome.execution_result.measurements_table:
                    tbl = outcome.execution_result.measurements_table
                    if "asset_id" in tbl.column_names:
                        assets = tbl.column("asset_id").to_pylist()
                        accepted_assets.update(a for a in assets if a)

        # 2. Audit against expected asset roster
        missing_assets: list[str] = []
        for expected in contract.expected_assets:
            if expected not in accepted_assets:
                missing_assets.append(expected)
                errors.append(
                    ValidationErrorItem(
                        code=ErrorCode.ERR_VAL_MISSING_ASSET,
                        severity=ErrorSeverity.ERROR,
                        message=(
                            f"Expected asset '{expected}' missing from accepted files in batch."
                        ),
                        remediation="Ensure files for all expected assets are supplied and valid.",
                    )
                )

        # 3. Detect cross-file telemetry conflicts on identical (asset, signal, timestamp)
        # Map: (asset_id, signal_id, timestamp_str) -> (value, filename)
        observed_points: dict[tuple[str, str, str], tuple[float | None, str]] = {}

        for outcome in outcomes:
            if outcome.result_state != JobResultState.ACCEPTED:
                continue
            if not outcome.execution_result or not outcome.execution_result.measurements_table:
                continue

            tbl = outcome.execution_result.measurements_table
            asset_col = tbl.column("asset_id").to_pylist()
            signal_col = tbl.column("signal_id").to_pylist()
            time_col = tbl.column("timestamp_utc").to_pylist()
            val_col = tbl.column("value").to_pylist()

            for asset, signal, t_val, val in zip(
                asset_col, signal_col, time_col, val_col, strict=False
            ):
                time_str = t_val.isoformat() if hasattr(t_val, "isoformat") else str(t_val)
                key = (str(asset), str(signal), time_str)

                if key in observed_points:
                    prev_val, prev_file = observed_points[key]
                    # Check for value disagreement
                    if prev_val != val:
                        # If both are numbers, check epsilon
                        disagrees = True
                        if isinstance(prev_val, (int, float)) and isinstance(val, (int, float)):
                            if abs(prev_val - val) < 1e-6:
                                disagrees = False

                        if disagrees:
                            errors.append(
                                ValidationErrorItem(
                                    code=ErrorCode.ERR_VAL_CROSS_FILE_DISAGREEMENT,
                                    severity=ErrorSeverity.ERROR,
                                    message=(
                                        f"Conflicting telemetry values for asset '{key[0]}', "
                                        f"signal '{key[1]}' at '{key[2]}': {prev_val} from "
                                        f"'{prev_file}' vs {val} from '{outcome.filename}'."
                                    ),
                                    remediation=(
                                        "Data steward resolution required. "
                                        "Zero speculative deduplication permitted."
                                    ),
                                )
                            )
                else:
                    observed_points[key] = (val, outcome.filename)

        return ReconciliationReport(
            errors=errors,
            warnings=warnings,
            missing_assets=sorted(missing_assets),
            accepted_assets=sorted(accepted_assets),
        )
