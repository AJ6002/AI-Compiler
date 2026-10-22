"""Upload and Handoff Manifest contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import ArchiveType, JobResultState


class FileEntry(BaseModel):
    """Metadata record for a single file within an admission upload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str = Field(..., description="Normalized relative path inside archive.")
    sha256: str = Field(..., description="Hex-encoded SHA-256 checksum.")
    byte_size: int = Field(..., ge=0, description="Size in bytes.")
    mime_type_detected: str = Field(..., description="Inspected content type.")


class UploadManifest(BaseContract):
    """Immutable admission record of an authorized client upload."""

    upload_id: str = Field(..., description="Unique upload identifier.")
    archive_type: ArchiveType = Field(..., description="Single XLSX or ZIP archive.")
    uploaded_at: datetime = Field(..., description="Server admission timestamp.")
    total_files: int = Field(..., ge=1, description="Total files discovered in upload.")
    total_compressed_bytes: int = Field(..., ge=0, description="Payload byte size.")
    files: list[FileEntry] = Field(..., min_length=1, description="Catalog of file entries.")


class HandoffManifest(BaseContract):
    """Machine-readable handoff manifest consumed downstream by AutoMLOps."""

    handoff_id: str = Field(..., description="Unique handoff identifier.")
    dataset_id: str = Field(..., description="Identifier of the published dataset.")
    result_state: JobResultState = Field(
        ...,
        description="Must be ACCEPTED for automated consumption.",
    )
    compiler_version: str = Field(..., description="Version of the compiler service.")
    contract_version: str = Field(..., description="Version of ClientContract validated against.")
    recipe_version: str | None = Field(
        default=None, description="Recipe version used if applicable."
    )
    measurement_tables: list[str] = Field(
        ...,
        min_length=1,
        description="URIs or relative paths to output Parquet tables.",
    )
    signal_dictionary_uri: str = Field(
        ..., description="URI to signal dictionary Parquet artifact."
    )
    provenance_map_uri: str = Field(..., description="URI to provenance map Parquet artifact.")
    validation_report_uri: str = Field(..., description="URI to validation-report.json.")
    signal_coverage: dict[str, float] = Field(
        default_factory=dict,
        description="Coverage percentage (0.0 to 1.0) per signal ID.",
    )
    assets_expected: int = Field(..., ge=0)
    assets_accepted: int = Field(..., ge=0)
    assets_missing: list[str] = Field(default_factory=list)
