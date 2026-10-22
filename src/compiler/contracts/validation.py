"""Validation Report contracts capturing quality audits and acceptance decisions."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import ErrorCode, ErrorSeverity, JobResultState


class ValidationErrorItem(BaseModel):
    """Specific diagnostic issue discovered during admission, parsing, or contract validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode = Field(..., description="Machine-readable error code.")
    severity: ErrorSeverity = Field(..., description="Severity level of the error.")
    message: str = Field(..., description="Human-readable description of the error.")
    sheet: str | None = Field(default=None, description="Affected worksheet name if known.")
    cell_coordinate: str | None = Field(
        default=None, description="Affected cell or range if known."
    )
    signal_path: str | None = Field(default=None, description="Affected semantic signal if known.")
    remediation: str = Field(..., description="Prescribed remediation guidance for data steward.")


class ValidationReport(BaseContract):
    """Validation report detailing compliance against ClientContract."""

    report_id: str = Field(..., description="Unique report identifier.")
    target_object_id: str = Field(..., description="Identifier of the validated file or dataset.")
    result_state: JobResultState = Field(
        ...,
        description="ACCEPTED, REVIEW_REQUIRED, UNSUPPORTED, or FAILED.",
    )
    errors: list[ValidationErrorItem] = Field(
        default_factory=list,
        description="Errors preventing automatic publication.",
    )
    warnings: list[ValidationErrorItem] = Field(
        default_factory=list,
        description="Advisory warnings.",
    )
    summary_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary metrics (row counts, signal coverage, missing counts).",
    )


class BatchValidationReport(BaseContract):
    """Batch-level validation report reconciling multiple files within an archive."""

    batch_id: str = Field(..., description="Batch or job identifier.")
    result_state: JobResultState = Field(..., description="Overall batch acceptance status.")
    files_expected: int = Field(..., ge=0)
    files_found: int = Field(..., ge=0)
    files_accepted: int = Field(..., ge=0)
    files_review_required: int = Field(..., ge=0)
    files_missing: list[str] = Field(default_factory=list)
    per_file_statuses: dict[str, JobResultState] = Field(default_factory=dict)
    batch_errors: list[ValidationErrorItem] = Field(default_factory=list)
