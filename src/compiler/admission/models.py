"""Pydantic models for admission and archive inspection results."""

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import ArchiveType, JobResultState
from src.compiler.contracts.manifests import FileEntry, UploadManifest
from src.compiler.contracts.validation import ValidationErrorItem


class InspectionOutcome(BaseModel):
    """Internal outcome of inspecting an archive or raw workbook bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    archive_type: ArchiveType
    detected_entries: list[FileEntry] = Field(default_factory=list)
    total_uncompressed_bytes: int = 0
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    warnings: list[ValidationErrorItem] = Field(default_factory=list)


class AdmissionResult(BaseModel):
    """Public deliverable returned by the Admission Gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_id: str = Field(..., description="Server-side immutable object identifier.")
    sha256: str = Field(..., description="SHA-256 cryptographic digest of the raw upload.")
    status: JobResultState = Field(..., description="ACCEPTED, FAILED, or REVIEW_REQUIRED.")
    archive_type: ArchiveType = Field(..., description="Identified payload type.")
    storage_uri: str | None = Field(default=None, description="Immutable storage URI if accepted.")
    manifest: UploadManifest | None = Field(
        default=None,
        description="Constructed UploadManifest if admitted.",
    )
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    warnings: list[ValidationErrorItem] = Field(default_factory=list)
