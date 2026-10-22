"""Signal Dictionary and Asset Mapping contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract


class SignalDefinition(BaseModel):
    """Semantic definition of a single measured signal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str = Field(..., description="Stable semantic identifier.")
    canonical_path: str = Field(
        ...,
        description="Hierarchical dot-delimited path (e.g., COMPRESSOR_1.STAGE_1.PRESSURE).",
    )
    canonical_unit: str = Field(..., description="Approved standard unit.")
    data_type: Literal["numeric", "text", "boolean", "datetime"] = Field(
        default="numeric",
        description="Data type of the signal value.",
    )
    description: str | None = Field(default=None, description="Human-readable description.")


class SignalDictionary(BaseContract):
    """Canonical catalog of versioned signals for a tenant/project."""

    dictionary_id: str = Field(..., description="Unique identifier for this dictionary.")
    version: str = Field(..., description="Semantic version string for signal definitions.")
    signals: dict[str, SignalDefinition] = Field(
        ...,
        description="Mapping of signal_id to its semantic definition.",
    )


class AssetMap(BaseContract):
    """Mapping from raw equipment serials/tags to canonical asset IDs."""

    map_id: str = Field(..., description="Unique identifier for this asset map.")
    version: str = Field(..., description="Version of the asset mapping rules.")
    mappings: dict[str, str] = Field(
        ...,
        description="Raw equipment tag or serial -> canonical asset_id.",
    )
    unmapped_policy: Literal["route_to_review", "reject"] = Field(
        default="route_to_review",
        description="Action when encountering an unknown asset tag.",
    )
