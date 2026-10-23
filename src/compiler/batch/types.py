"""Data structures and types for multi-file batch assembly and reconciliation."""

from __future__ import annotations

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import JobResultState
from src.compiler.contracts.validation import BatchValidationReport, ValidationReport
from src.compiler.execution.executor import ExecutionResult


class FileProcessingOutcome(BaseModel):
    """Execution and validation outcome for a single file within a batch."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    filename: str = Field(..., description="Original filename within batch archive.")
    object_id: str = Field(..., description="Unique file admission identifier.")
    sha256: str = Field(..., description="Hex SHA-256 digest of raw file.")
    result_state: JobResultState = Field(..., description="File-level verdict.")
    validation_report: ValidationReport = Field(..., description="Validation report for this file.")
    execution_result: ExecutionResult | None = Field(
        default=None,
        description="Arrow execution result if plan executed successfully.",
    )
    asset_id: str | None = Field(default=None, description="Discovered asset identifier.")


class BatchAssemblyResult(BaseModel):
    """Aggregate result from multi-file batch assembly and cross-file reconciliation."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    batch_id: str = Field(..., description="Unique batch or job identifier.")
    result_state: JobResultState = Field(..., description="Overall batch acceptance status.")
    batch_measurements_table: pa.Table | None = Field(
        default=None,
        description="Concatenated Arrow measurements table across accepted files.",
    )
    batch_provenance_table: pa.Table | None = Field(
        default=None,
        description="Concatenated Arrow provenance table across accepted files.",
    )
    batch_validation_report: BatchValidationReport = Field(
        ...,
        description="Batch-level validation and reconciliation report.",
    )
    per_file_outcomes: list[FileProcessingOutcome] = Field(
        default_factory=list,
        description="Per-file processing outcomes in the batch.",
    )
