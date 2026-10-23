"""Data structures and types for structural discovery and layout recognition."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.contracts.structure import RegionBoundary


class CellTypeSignature(StrEnum):
    """Categorized cell data type signatures for layout analysis."""

    EMPTY = "z"
    TEXT = "s"
    NUMERIC = "n"
    DATETIME = "d"
    DURATION = "duration"
    FORMULA = "f"
    BOOLEAN = "b"
    ERROR = "e"


class HeaderPath(BaseModel):
    """Reconstructed hierarchical header path for a column."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    column_index: int = Field(..., ge=1, description="1-indexed column position.")
    path: str = Field(..., description="Full dot-separated path, e.g. DISPENSER_1.HOSE_A.PRESSURE")
    leaf_name: str = Field(..., description="Leaf column label.")
    ancestors: list[str] = Field(default_factory=list, description="Ordered parent group names.")
    source_coordinates: list[str] = Field(
        default_factory=list,
        description="A1 coordinates of cells contributing to this path.",
    )


class MetadataEntry(BaseModel):
    """Single key-value metadata item extracted outside measurement tables."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(..., description="Metadata attribute name.")
    value: Any = Field(..., description="Metadata value.")
    key_coordinate: str = Field(..., description="Cell coordinate where key was found.")
    value_coordinate: str | None = Field(default=None, description="Cell coordinate of value.")


class TableRegionLayout(BaseModel):
    """Identified data table region with its header band and resolved columns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    boundary: RegionBoundary = Field(..., description="Bounding box of the entire table.")
    header_rows: list[int] = Field(..., description="1-indexed row indices of the header band.")
    data_start_row: int = Field(..., ge=1, description="1-indexed row where data starts.")
    data_end_row: int = Field(..., ge=1, description="1-indexed row where data ends.")
    columns: list[HeaderPath] = Field(..., description="Resolved columns across the table.")


class DiscoveredLayout(BaseModel):
    """Full structural layout discovered for a single worksheet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet_name: str = Field(..., description="Worksheet name.")
    tables: list[TableRegionLayout] = Field(
        default_factory=list, description="Discovered data tables."
    )
    metadata_entries: list[MetadataEntry] = Field(
        default_factory=list, description="Extracted metadata items."
    )
    unassigned_regions: list[RegionBoundary] = Field(
        default_factory=list, description="Unrecognized or dispersed regions."
    )
    verdict: JobResultState = Field(
        default=JobResultState.ACCEPTED,
        description="ACCEPTED or REVIEW_REQUIRED.",
    )
    error_codes: list[ErrorCode] = Field(
        default_factory=list,
        description="Error codes explaining REVIEW_REQUIRED verdict.",
    )
    diagnostic_messages: list[str] = Field(
        default_factory=list,
        description="Human-readable explanations of structural findings.",
    )
