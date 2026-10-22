"""Client Contract specifying validation criteria, allowed units, and operational policies."""

from pydantic import Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import DuplicatePolicy, PartialBatchPolicy


class ClientContract(BaseContract):
    """Client-approved specification of signals, units, cadence, and validation policies."""

    contract_id: str = Field(..., description="Unique client contract identifier.")
    version: str = Field(..., description="Semantic version string for this contract.")
    expected_assets: list[str] = Field(
        ...,
        description="Roster of expected asset identifiers for this project.",
    )
    required_signals: list[str] = Field(
        ...,
        description="List of mandatory signal IDs that must be present.",
    )
    optional_signals: list[str] = Field(
        default_factory=list,
        description="List of optional signal IDs.",
    )
    allowed_units: dict[str, list[str]] = Field(
        ...,
        description="Mapping of signal_id -> allowed unit strings.",
    )
    timezone: str = Field(default="UTC", description="Expected timezone string (e.g., 'UTC').")
    expected_cadence_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Expected sampling interval in seconds if regular.",
    )
    allowed_missing_tokens: list[str] = Field(
        default_factory=lambda: ["NA", "N/A", "-", "null", "NULL", ""],
        description="Tokens safely normalized to null while preserving raw token in null_reason.",
    )
    duplicate_timestamp_policy: DuplicatePolicy = Field(
        default=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        description="Handling policy for duplicate timestamps on the same asset.",
    )
    partial_batch_policy: PartialBatchPolicy = Field(
        default=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
        description="Policy when some files in a batch accept and others require review.",
    )
