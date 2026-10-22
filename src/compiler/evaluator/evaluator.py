"""Independent comparison evaluator comparing compiler outputs against oracle fixtures."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import JobResultState
from src.compiler.evaluator.oracle import OracleFixture


class EvaluationOutcome(BaseModel):
    """Result of evaluating actual compiler outputs against an OracleFixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool = Field(..., description="True only if all evaluation criteria pass.")
    fixture_id: str = Field(..., description="Fixture evaluated.")
    decision_match: bool = Field(..., description="Whether result_state matches oracle.")
    row_count_match: bool = Field(..., description="Whether row count matches expected.")
    signal_coverage_match: bool = Field(..., description="Whether required signals are extracted.")
    error_codes_match: bool = Field(..., description="Whether expected error codes fired.")
    value_divergence_count: int = Field(default=0, ge=0)
    provenance_missing_count: int = Field(default=0, ge=0)
    failures: list[str] = Field(
        default_factory=list,
        description="List of detailed failure diagnostic messages.",
    )


class DatasetEvaluator:
    """Independent verification engine that audits compiler output against the test oracle."""

    def evaluate(
        self,
        actual_result_state: JobResultState,
        actual_records: list[dict[str, Any]],
        oracle: OracleFixture,
        actual_error_codes: list[str] | None = None,
    ) -> EvaluationOutcome:
        """Evaluate compilation outcome and extracted records against the oracle."""
        failures: list[str] = []
        actual_error_codes = actual_error_codes or []

        # 1. Decision Match
        decision_match = actual_result_state == oracle.expected_result_state
        if not decision_match:
            failures.append(
                f"Decision mismatch: expected {oracle.expected_result_state}, "
                f"got {actual_result_state}"
            )

        # 2. Expected Error Codes Match
        expected_codes_set = set(oracle.expected_error_codes)
        actual_codes_set = set(actual_error_codes)
        missing_errors = expected_codes_set - actual_codes_set
        error_codes_match = len(missing_errors) == 0
        if not error_codes_match:
            failures.append(f"Expected error codes missing: {missing_errors}")

        # 3. Row Count Check
        actual_row_count = len(actual_records)
        row_count_match = actual_row_count == oracle.expected_row_count
        if not row_count_match:
            failures.append(
                f"Row count mismatch: expected {oracle.expected_row_count}, got {actual_row_count}"
            )

        # 4. Signal Coverage & Value Checks
        extracted_signals: set[str] = set()
        provenance_missing = 0
        value_divergence = 0

        for r_idx, rec in enumerate(actual_records):
            # Check provenance tracking
            if "provenance_id" not in rec or not rec["provenance_id"]:
                provenance_missing += 1

            # Check signal presence
            sig = rec.get("signal_id")
            if sig:
                extracted_signals.add(sig)

            # Check observation key structure
            if "observation_key" in rec and not rec["observation_key"]:
                failures.append(f"Record {r_idx} missing non-empty observation_key")

        # Check required signals from oracle
        missing_signals = set(oracle.expected_signals.keys()) - extracted_signals
        signal_coverage_match = len(missing_signals) == 0
        if not signal_coverage_match and oracle.expected_result_state == JobResultState.ACCEPTED:
            failures.append(f"Missing mandatory signals: {missing_signals}")

        if provenance_missing > 0 and oracle.expected_result_state == JobResultState.ACCEPTED:
            failures.append(
                f"Provenance missing on {provenance_missing} records: source cell links required"
            )

        passed = len(failures) == 0

        return EvaluationOutcome(
            passed=passed,
            fixture_id=oracle.fixture_id,
            decision_match=decision_match,
            row_count_match=row_count_match,
            signal_coverage_match=signal_coverage_match,
            error_codes_match=error_codes_match,
            value_divergence_count=value_divergence,
            provenance_missing_count=provenance_missing,
            failures=failures,
        )
