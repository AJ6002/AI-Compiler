"""Configuration settings and security thresholds for the admission gate."""

from pydantic import BaseModel, ConfigDict, Field


class AdmissionConfig(BaseModel):
    """Configurable security boundaries and expansion thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_compressed_bytes: int = Field(
        default=100 * 1024 * 1024,
        description="Maximum raw upload size in bytes (default: 100 MB).",
    )
    max_expanded_bytes: int = Field(
        default=500 * 1024 * 1024,
        description="Maximum cumulative uncompressed size in bytes (default: 500 MB).",
    )
    max_file_count: int = Field(
        default=100,
        description="Maximum number of files allowed inside a zip archive.",
    )
    max_expansion_ratio: float = Field(
        default=100.0,
        description="Maximum ratio of uncompressed bytes to compressed bytes.",
    )
    max_single_entry_bytes: int = Field(
        default=100 * 1024 * 1024,
        description="Maximum uncompressed size of a single archive entry.",
    )
    max_nesting_depth: int = Field(
        default=1,
        description="Maximum archive nesting depth (1 = no nested zip files allowed).",
    )
    allowed_extensions: list[str] = Field(
        default_factory=lambda: ["xlsx", "zip"],
        description="Allowed file extensions.",
    )
